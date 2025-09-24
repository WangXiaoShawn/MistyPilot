
import os, sys, time, pathlib, json, datetime                                ### 基础库
from typing import Optional, Dict, Any, List                                  ### typing

sys.path.append(os.path.dirname(__file__))                                    ### 确保能 import 同目录下的 I/O

from CUBS_Misty_Record import (                                                 ### Misty 录音 I/O
    start_misty_recording,                                                    ### 开始录音（远端固定名）
    stop_misty_recording,                                                     ### 停止录音
    download_misty_recording,                                                 ### 下载到本地
)

# -------- 固定存储策略（覆盖写） --------
current_file_dir = pathlib.Path(__file__).parent.absolute()
SAVE_DIR   = current_file_dir / "records"                                     ### 音频/文本固定在 ./records
AUDIO_NAME = "misty_audio_temp_record.wav"                                    ### 固定音频名（每次覆盖）
TEXT_NAME  = "misty_audio_temp_record.txt"                                    ### 固定文本名（每次覆盖）

DEBOUNCE_SEC  = 0.5                                                           ### 防抖秒数
_last_toggle  = 0.0                                                           ### 上次触发时间（monotonic）
_is_recording = False                                                         ### 当前是否在录音

# -------- 日志文件路径：固定，不读环境 --------
DEFAULT_LOG_PATH = current_file_dir / "daily_important_event.json"            ### 按你要求写死

# -------- OpenAI：显式硬编码 API Key（你提供的值） --------

def load_config(config_filename="MistyPilot_config.json"):
    """
    加载上一层目录的配置文件
    :param config_filename: 配置文件名 (默认 config.json)
    :return: 配置字典 config
    """
    # 获取当前文件所在目录
    current_dir = os.path.dirname(__file__)
    
    # 拼接到上一层目录
    config_path = os.path.join(current_dir, "..", config_filename)
    config_path = os.path.abspath(config_path)  # 转绝对路径
    
    # 读取 JSON 配置
    with open(config_path, "r") as f:
        config = json.load(f)
    
    return config

cfg = load_config("MistyPilot_config.json")  
OPENAI_API_KEY = cfg["openai_api_key"]


# ======================= OpenAI & STT =======================

def _get_client():                                                            ### 获取 OpenAI 客户端（带缓存）
    from openai import OpenAI                                                 ### 延迟导入，避免未用时报依赖
    global _openai_client                                                     ### 使用模块级缓存
    if _openai_client is None:                                                ### 首次创建
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)                       ### 用硬编码密钥初始化
    return _openai_client                                                     ### 返回客户端

def _transcribe_to_text(audio_path: pathlib.Path) -> str:                     ### 调用 STT 转英文文本
    if not audio_path.exists():                                               ### 文件存在性检查
        raise FileNotFoundError(f"音频不存在: {audio_path}")                  ### 抛异常
    client = _get_client()                                                    ### 获取客户端
    with open(audio_path, "rb") as f:                                         ### 以二进制读音频
        resp = client.audio.transcriptions.create(                            ### 创建转录请求
            model="gpt-4o-mini-transcribe",                                   ### 转录模型
            prompt=("You are a robot named Misty. Everything you hear "
                    "should be transcribed and output in English only."),     ### 强制英文输出
            file=f                                                            ### 上传文件
        )
    text = getattr(resp, "text", None) or getattr(resp, "transcript", "")     ### 兼容不同返回字段
    return text or str(resp)                                                  ### 兜底：字符串化

# ======================= daily_important_event.json 工具 =======================

def _now_local() -> datetime.datetime:                                        ### 取本地时间
    return datetime.datetime.now()                                            ### 简单本地时间即可

def ensure_daily_event_log_exists(path: pathlib.Path) -> pathlib.Path:        ### 确保日志文件存在且为 dict 根
    path.parent.mkdir(parents=True, exist_ok=True)                            ### 确保目录存在
    if not path.exists():                                                     ### 不存在则创建空 dict
        path.write_text("{}", encoding="utf-8")                               ### 写入空对象
        return path                                                           ### 返回路径
    try:
        data = json.loads(path.read_text("utf-8"))                            ### 读取现有 JSON
        if not isinstance(data, dict):                                        ### 校验根是对象
            raise ValueError("root is not object")                            ### 非对象则抛异常
    except Exception:                                                         ### 读/解析失败
        try:
            path.rename(path.with_suffix(path.suffix + ".bak"))               ### 备份坏文件
        except Exception:
            pass                                                              ### 备份失败忽略
        path.write_text("{}", encoding="utf-8")                               ### 重建为空对象
    return path                                                               ### 返回路径

def add_event_to_daily_log_default(event: str, content: Any,
                                   log_path: pathlib.Path = DEFAULT_LOG_PATH) -> List[Dict[str, Any]]:
    """
    增量写入到 daily_important_event.json
    根结构: { "YYYY-MM-DD": [ {"time","event","content"}, ... ] }
    - event: 事件名（此场景为 "take_audio"）
    - content: 任意内容（这里用转录文本字符串）
    返回：追加后的当天列表
    """
    log_path = ensure_daily_event_log_exists(log_path)                        ### 确保文件可用
    now  = _now_local()                                                       ### 当前时间
    dkey = now.strftime("%Y-%m-%d")                                           ### 日期键
    tstr = now.strftime("%H:%M:%S")                                           ### 时间字符串

    try:
        data = json.loads(log_path.read_text("utf-8"))                        ### 读现有 JSON
    except Exception:
        data = {}                                                             ### 读失败重建

    if not isinstance(data, dict):                                            ### 容错：根应为 dict
        data = {}                                                             ### 重设为空 dict

    day_list = data.get(dkey)                                                 ### 当天列表
    if not isinstance(day_list, list):                                        ### 不存在则创建
        day_list = []
        data[dkey] = day_list

    day_list.append({"time": tstr, "event": event, "content": content})       ### 增量追加条目

    tmp = log_path.with_suffix(log_path.suffix + ".tmp")                      ### 临时文件路径
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),            ### 写临时 JSON
                   encoding="utf-8")                                          ### UTF-8 编码
    tmp.replace(log_path)                                                     ### 原子替换
    return day_list                                                           ### 返回当天列表

# ======================= 控制接口 =======================

def reset_toggle_state() -> None:                                             ### 手动复位（异常后使用）
    global _is_recording                                                      ### 引用模块级状态
    _is_recording = False                                                     ### 复位为未录音

def cb_record_audio(evt: Dict[str, Any], misty_ip: str,
                     api_key: Optional[str] = None) -> None:
    """
    This is Misty's recording callback.
    Use it when the user wants to record something by speaking.
    """
    global _last_toggle, _is_recording                                        ### 状态引用
    now = time.monotonic()                                                    ### 单调时钟
    if (now - _last_toggle) < DEBOUNCE_SEC:                                   ### 防抖：过快触发直接忽略
        return                                                                ### 返回
    _last_toggle = now                                                        ### 刷新触发时间

    # 分支1：开始录音
    if not _is_recording:                                                     ### 未在录音
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)                       ### 确保保存目录
            start_misty_recording(misty_ip)                                   ### 请求开始录音
            _is_recording = True                                              ### 标记录音中
            print(f"[record] STARTED @ {misty_ip} -> {AUDIO_NAME}")           ### 日志
        except Exception as e:
            _is_recording = False                                             ### 启动失败回滚
            print(f"[record] start failed: {e}")                              ### 报错
        return                                                                ### 结束分支1

    # 分支2：停止→下载→转录
    try:
        try:
            stop_misty_recording(misty_ip)                                    ### 请求停止录音
        except Exception as e:
            print(f"[record] stop warn: {e}")                                 ### 停止失败也尝试下载

        tmp_path = download_misty_recording(misty_ip, SAVE_DIR)               ### 下载远端固定名到本地
        tmp_path = pathlib.Path(tmp_path)                                     ### 兼容 str/Path 返回
        fixed_audio = SAVE_DIR / AUDIO_NAME                                   ### 固定目标路径

        try:
            if tmp_path.exists():                                             ### 下载结果存在
                tmp_path.replace(fixed_audio)                                 ### 覆盖为固定名
            else:
                print(f"[record] unexpected: file not found {tmp_path}")      ### 异常提示
        except Exception as e:
            print(f"[record] rename failed (keep tmp): {e}")                  ### 重命名失败
            fixed_audio = tmp_path                                            ### 兜底：保留原路径

        print(f"[record] SAVED (overwritten): {fixed_audio}")                 ### 保存日志

        # —— 立刻转录 —— #
        try:
            text = _transcribe_to_text(fixed_audio)                           ### 执行转录
            fixed_txt = SAVE_DIR / TEXT_NAME                                  ### 文本目标路径
            fixed_txt.write_text(text or "", encoding="utf-8")                ### 覆盖写入
            print(f"[transcribe] OK -> {fixed_txt}\n{text}")                  ### 打印结果与路径

            # —— 增量写 daily_important_event.json —— #
            add_event_to_daily_log_default(event="take_audio",                ### 事件名：take_audio
                                            content=text)                     ### 内容：纯文本转录
        except Exception as e:
            print(f"[transcribe] failed: {e}")                                ### 转录失败日志

    except Exception as e:
        print(f"[record] download failed: {e}")                               ### 下载流程失败
    finally:
        _is_recording = False                                                 ### 无论如何回到未录音态
