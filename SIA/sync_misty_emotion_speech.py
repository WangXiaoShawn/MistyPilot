# -*- coding: utf-8 -*-                                                             ### 文件编码
# ==================== DEPRECATED / 已废弃 ====================
# 此文件已废弃，不再使用 Misty 播放音频
# 请使用以下替代方案：
# - streaming_slow_thinking_emotion_speech.py (流式本地播放)
# - misty_fast_thinking_emotion_speech.py (快思考本地播放)
# =============================================================
# one_shot_tts_misty.py                                                             ### 文件名
# 功能：OpenAI TTS -> 上传到 Misty -> 播放（可与动作并行；用 MP3 时长自动驱动动作 pause_before_reset；支持 emotion 自动填充 speed/instructions/动作）  ### 说明

import base64                                                                        ### base64 编解码
import time                                                                          ### 睡眠/时间戳
import requests                                                                      ### 调 Misty HTTP API
import io                                                                            ### BytesIO 给 mutagen 用
import threading                                                                     ### 并行动作线程/文件锁
import json                                                                          ### JSON 读写
from typing import Optional, Dict, Any, Tuple, Callable, List                        ### 类型注解
from openai import OpenAI                                                            ### OpenAI 同步客户端
import asyncio                                                                       ### 异步薄封装用

# === 你的动作函数（来自自定义模块 emotion_actions.py） ==============================================
from .emotion_actions import (                                                        ### 导入所有需要的动作
    perform_arousal_action,          ### 激动/亢奋
    perform_excitement_action,       ### 兴奋/喜悦
    perform_sleepiness_action,       ### 困倦
    perform_misery_action,           ### 痛苦
    perform_distress_action,         ### 焦灼/苦恼
    perform_pleasure_action,         ### 愉快
    perform_contentment_action,      ### 满足/安逸
    perform_depression_action,       ### 抑郁
)

# ------------------------ 情绪 -> 语速/指令 映射 -------------------------------------------------------

EMOTION_SPEED = {                                                                    ### 情绪到推荐语速
    "Arousal": 1.05,                                                                  ### 激动/亢奋：略快
    "Excitement": 1.05,                                                               ### 兴奋/喜悦：略快
    "Distress": 1.05,                                                                 ### 焦灼/苦恼：略快+短停顿
    "Pleasure": 1.0,                                                                 ### 愉快：常速或略快
    "Contentment": 0.9,                                                              ### 满足/安逸：略慢
    "Sleepiness": 0.9,                                                               ### 困倦：慢
    "Depression": 0.9,                                                               ### 抑郁：慢
    "Misery": 0.9,                                                                   ### 痛苦：慢
}

EMOTION_INSTRUCTIONS = {                                                             ### 情绪到风格指令
    "Arousal": (
        "Speak in a highly energized, urgent tone. Use a slightly fast pace "
        "without rushing. Keep articulation crisp, insert brief pauses to segment ideas, "
        "and emphasize key words—avoid machine-gun delivery."
    ),
    "Excitement": (
        "Speak in an enthusiastic, cheerful tone. Maintain a slightly fast pace with lively intonation, "
        "occasional upward endings, and short pauses. Keep it bright, clear, and natural."
    ),
    "Pleasure": (
        "Speak in a warm, pleasant tone. Use a near-normal or slightly brisk pace with smooth phrasing, "
        "light emphasis on positive words, and gentle melodic movement."
    ),
    "Contentment": (
        "Speak in a calm, relaxed tone. Keep a normal to slightly slow pace with even intonation, "
        "balanced pauses, and an unhurried, friendly delivery."
    ),
    "Sleepiness": (
        "Speak in a drowsy, relaxed tone. Use a slow pace, lower pitch, and longer pauses; "
        "minimize pitch excursions and soften the delivery while staying intelligible."
    ),
    "Depression": (
        "Speak in a subdued, flat tone. Keep a slow pace with low pitch and longer, more frequent pauses; "
        "reduce prosodic variation and keep sentences short and restrained."
    ),
    "Misery": (
        "Speak in a pained, sorrowful tone. Use a slow pace with noticeable pauses, slight tremble acceptable, "
        "and downward sentence endings; keep volume restrained and controlled."
    ),
    "Distress": (
        "Speak in a tense, anxious tone. Maintain a slightly fast pace with clipped phrases, "
        "short irregular pauses conveying urgency, and sharp emphasis on key words while remaining clear."
    ),
}

# ------------------------ 情绪 -> 动作函数映射 + 别名规范化 ---------------------------------------------

EMOTION_ACTIONS = {                                                                  ### 情绪到动作函数
    "Arousal":      perform_arousal_action,                                          ### 激动
    "Excitement":   perform_excitement_action,                                       ### 兴奋
    "Distress":     perform_distress_action,                                         ### 焦灼
    "Pleasure":     perform_pleasure_action,                                         ### 愉快
    "Contentment":  perform_contentment_action,                                      ### 满足
    "Sleepiness":   perform_sleepiness_action,                                       ### 困倦
    "Depression":   perform_depression_action,                                       ### 抑郁
    "Misery":       perform_misery_action,                                           ### 痛苦
}

_EMOTION_ALIASES = {                                                                 ### 别名->规范名（小写匹配）
    "arousal":"Arousal", "激动":"Arousal", "亢奋":"Arousal",
    "excitement":"Excitement", "兴奋":"Excitement", "喜悦":"Excitement",
    "distress":"Distress", "焦虑":"Distress", "焦灼":"Distress", "苦恼":"Distress",
    "pleasure":"Pleasure", "愉快":"Pleasure",
    "contentment":"Contentment", "满足":"Contentment", "安逸":"Contentment",
    "sleepiness":"Sleepiness", "困倦":"Sleepiness", "犯困":"Sleepiness", "想睡":"Sleepiness",
    "depression":"Depression", "抑郁":"Depression", "低落":"Depression",
    "misery":"Misery", "痛苦":"Misery",
}

def _canonical_emotion(e: Optional[str]) -> Optional[str]:
    """把输入情绪规范化到英文主键；未知则原样返回"""                                   ###
    if not e:                                                                         ### 空值
        return None                                                                   ### 返回 None
    if e in EMOTION_SPEED:                                                            ### 已是规范键
        return e                                                                      ### 直接返回
    key = e.strip().casefold()                                                        ### 去空格小写化
    return _EMOTION_ALIASES.get(key, e)                                               ### 映射失败则原样返回

# ------------------------ 全局锁：防并发写坏 JSON -------------------------------------------------------
_json_lock = threading.Lock()                                                         ### 保护 JSON 追加写

def _init_tts_json_file(json_file: str = "temp_emotion_speaking_mp3.json") -> None:  ### 清空/创建保存文件
    """在一次批处理开始前清空文件为 []。若不存在则创建。"""                                     ###
    try:                                                                              ### 保护性执行
        with _json_lock:                                                              ### 并发安全
            with open(json_file, "w", encoding="utf-8") as f:                         ### 以写模式打开（覆盖）
                json.dump([], f, ensure_ascii=False, indent=2)                        ### 写入空数组
    except Exception as e:                                                            ### 捕获异常
        print(f"[WARN] init {json_file} failed: {e}")                                 ### 打印告警

# ------------------------ 辅助：MP3 时长计算 ------------------------------------------------------------

def _synchsafe_to_int(bs: bytes) -> int:                                             ### 解析 ID3v2 synchsafe 大小
    return (bs[0] << 21) | (bs[1] << 14) | (bs[2] << 7) | bs[3]                       ### bit-packed

def _skip_id3v2(audio_bytes: bytes) -> int:                                          ### 跳过 ID3v2 头部，返回偏移
    if len(audio_bytes) >= 10 and audio_bytes[0:3] == b"ID3":                         ### 检查 ID3
        size = _synchsafe_to_int(audio_bytes[6:10])                                   ### 有效负载大小
        return 10 + size                                                              ### 头(10) + 负载
    return 0                                                                          ### 无 ID3

# 比特率表/采样率表 -----------------------------------------------------------------
_BITRATE_TABLE = {
    3: { 3: [0,32,64,96,128,160,192,224,256,288,320,352,384,416,448,0],
         2: [0,32,48,56,64,80,96,112,128,160,192,224,256,320,384,0],
         1: [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0], },
    2: { 3: [0,32,48,56,64,80,96,112,128,144,160,176,192,224,256,0],
         2: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0],
         1: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0], },
    0: { 3: [0,32,48,56,64,80,96,112,128,144,160,176,192,224,256,0],
         2: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0],
         1: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0], },
}
_SAMPLERATE_TABLE = { 3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000] }

def _first_frame_bitrate_samplerate(audio_bytes: bytes) -> Tuple[Optional[int], Optional[int]]:
    """解析首帧估计比特率/采样率（CBR 情况较准，VBR 仅粗估）"""                            ###
    off = _skip_id3v2(audio_bytes)                                                    ### 跳过 ID3
    end = min(len(audio_bytes) - 4, off + 4096)                                       ### 限定扫描窗口
    i = off                                                                           ### 起始偏移
    while i < end:                                                                    ### 循环扫描
        b0 = audio_bytes[i]                                                           ### 当前字节
        b1 = audio_bytes[i+1]                                                         ### 下一字节
        if b0 == 0xFF and (b1 & 0xE0) == 0xE0:                                        ### 0xFFE 同步
            hdr = int.from_bytes(audio_bytes[i:i+4], "big")                           ### 4 字节头
            ver_id   = (hdr >> 19) & 0b11                                             ### 版本位
            layer    = (hdr >> 17) & 0b11                                             ### 层位
            br_idx   = (hdr >> 12) & 0b1111                                           ### 比特率索引
            sr_idx   = (hdr >> 10) & 0b11                                             ### 采样率索引
            if ver_id == 1 or layer == 0 or br_idx == 0xF or sr_idx == 0x3:           ### 非法值
                i += 1; continue
            if ver_id not in _BITRATE_TABLE or layer not in _BITRATE_TABLE[ver_id]:   ### 不支持组合
                i += 1; continue
            bitrate_kbps = _BITRATE_TABLE[ver_id][layer][br_idx]                      ### kbps
            if bitrate_kbps == 0:                                                     ### free/坏帧
                i += 1; continue
            samplerate = _SAMPLERATE_TABLE.get(ver_id, [None, None, None])[sr_idx]    ### Hz
            if not samplerate:
                i += 1; continue
            return bitrate_kbps, samplerate                                           ### 返回估计
        i += 1
    return None, None

def _mp3_duration_seconds(audio_bytes: bytes) -> float:
    """计算 mp3 时长(秒)。优先用 mutagen，失败则用首帧比特率降级估算。"""                   ###
    try:
        from mutagen.mp3 import MP3                                                   ### 尝试用 mutagen
        return MP3(io.BytesIO(audio_bytes)).info.length                               ### 精确长度
    except Exception:
        pass                                                                          ### 无 mutagen/失败则降级
    id3_skip = _skip_id3v2(audio_bytes)                                               ### ID3 大小
    br_kbps, _ = _first_frame_bitrate_samplerate(audio_bytes)                         ### 首帧 kbps
    if br_kbps and br_kbps > 0:                                                       ### 有效比特率
        bits = max(0, (len(audio_bytes) - id3_skip)) * 8                              ### 去除 ID3 后比特数
        return bits / (br_kbps * 1000.0)                                              ### 近似秒数（CBR 准确）
    DEFAULT_KBPS = 128                                                                ### 兜底 128kbps
    return (len(audio_bytes) * 8) / (DEFAULT_KBPS * 1000.0)                           ### 粗估

# ------------------------ 并发安全地追加写 JSON ---------------------------------------------------------

def _append_tts_json_record(                                                          ### 增量写入一条记录
    text: str,                                                                        ### 说话文本
    emotion: Optional[str],                                                           ### 情绪（规范名或 None）
    mp3_b64: str,                                                                     ### mp3 的 base64 字符串
    duration_sec: Optional[float] = None,                                             ### NEW: 音频时长（秒）
    json_file: str = "temp_emotion_speaking_mp3.json",                                ### 保存文件名
) -> None:                                                                            ### 无返回
    """增量保存：读取现有 list，append 当前 {text, emotion, mp3, duration_sec}，再写回。"""      ###
    try:
        with _json_lock:                                                              ### 并发写保护
            arr = []
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    arr = json.load(f)
                    if not isinstance(arr, list):
                        arr = []
            except FileNotFoundError:
                arr = []
            record = {"text": text, "emotion": emotion, "mp3": mp3_b64}
            if duration_sec is not None:                                              ### NEW: 如果提供了时长
                record["duration_sec"] = duration_sec                                 ### NEW: 保存到 JSON
            arr.append(record)
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(arr, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] failed to write {json_file}: {e}")

# ------------------------ HTTP 重试小工具 ---------------------------------------------------------------

def _post_with_retry(url: str, json_body: Dict[str, Any], timeout: int, retries: int = 2, backoff: float = 0.5):
    """对 requests.post 加一个简易指数退避重试。"""                                     ###
    last = None
    for i in range(retries + 1):
        try:
            r = requests.post(url, json=json_body, timeout=timeout)                   ### 发送请求
            r.raise_for_status()                                                      ### HTTP 错误抛出
            return r                                                                  ### 成功返回
        except Exception as e:
            last = e
            if i >= retries:
                break                                                                 ### 用尽重试
            time.sleep(backoff * (2 ** i))                                            ### 退避等待
    raise last                                                                         ### 最终失败向上抛

# ------------------------ 主函数：生成→上传→播放→（并行动作，按时长等待复位） --------------------------

def misty_humanlike_speaking(                                                         ### one-shot: TTS -> upload -> play
    openai_api_key: str,                                                              ### OpenAI API key
    misty_ip: str,                                                                    ### Misty 机器人 IP
    text: str,                                                                        ### 待合成文本
    model: str = "gpt-4o-mini-tts",                                                   ### TTS 模型
    voice: str = "coral",                                                             ### TTS 声音
    instructions: Optional[str] = None,                                               ### 说话风格（若 emotion 给定且此处 None，则自动填充）
    response_format: str = "mp3",                                                     ### 音频容器：mp3|wav|flac|aac|opus|pcm（仅 mp3 计算时长）
    filename_on_misty: Optional[str] = "openai_tts_temp.mp3",                         ### Misty 保存的文件名
    speed: Optional[float] = None,                                                    ### TTS 语速（若 emotion 给定且此处 None，则自动填充）
    volume: int = 80,                                                                 ### 播放音量 0~100
    overwrite_existing: bool = True,                                                  ### 是否覆盖同名文件
    play_now: bool = False,                                                           ### /api/audio 的 ImmediatelyApply（非播放）
    auto_unique_name: bool = False,                                                   ### 是否在文件名后加时间戳避免覆盖
    timeout_upload_sec: int = 60,                                                     ### 上传 HTTP 超时 (增加到60秒)
    timeout_play_sec: int = 120,                                                      ### 播放 HTTP 超时 (增加到120秒，解决吞字问题)
    block_until_finished: bool = True,                                                ### 是否阻塞直到完成（播放/动作）
    fudge_seconds: float = 0.5,                                                       ### 语音尾部缓冲，避免“抢尾”
    emotion: Optional[str] = None,                                                    ### 情绪标签：自动填充 speed/instructions/动作

    # 并行动作相关参数
    action_func: Optional[Callable[..., None]] = None,                                ### 动作函数（如 perform_excitement_action）
    action_kwargs: Optional[Dict[str, Any]] = None,                                   ### 传给动作函数的其它参数
    action_start_offset: float = 0.0,                                                 ### 播放触发后动作延时启动（秒）
    run_action_in_thread: bool = True,                                                ### 是否在后台线程运行动作
    join_action_when_block: bool = True,                                              ### 阻塞模式下是否等待动作线程结束
) -> Dict[str, Any]:
    assert response_format in {"mp3","wav","flac","aac","opus","pcm"}, "Invalid response_format"  ### 校验格式

    canonical = _canonical_emotion(emotion)                                            ### 规范化情绪名
    if canonical is not None:                                                          ### 若给了情绪
        if speed is None and canonical in EMOTION_SPEED:                               ### 自动语速
            speed = EMOTION_SPEED[canonical]
        if instructions is None and canonical in EMOTION_INSTRUCTIONS:                 ### 自动风格
            instructions = EMOTION_INSTRUCTIONS[canonical]
    emotion = canonical                                                                ### 回写规范情绪

    if not filename_on_misty:
        filename_on_misty = f"openai_tts_{int(time.time())}.{response_format}"         ### 兜底文件名
    if auto_unique_name:
        base, dot, ext = filename_on_misty.partition(".")
        filename_on_misty = f"{base}_{int(time.time())}.{ext or response_format}"

    client = OpenAI(api_key=openai_api_key)                                            ### 初始化 OpenAI 客户端
    create_kwargs = {                                                                  ### TTS 基本参数
        "model": model, "voice": voice, "input": text, "response_format": response_format
    }
    if instructions is not None:
        create_kwargs["instructions"] = instructions
    if speed is not None:
        create_kwargs["speed"] = float(speed)

    resp = client.audio.speech.create(**create_kwargs)                                 ### 同步生成音频
    audio_bytes = resp.read()                                                          ### 读取音频字节

    duration_sec = _mp3_duration_seconds(audio_bytes) if response_format == "mp3" else 0.0  ### 仅 mp3 算时长

    b64 = base64.b64encode(audio_bytes).decode("ascii")                                ### 将字节转 base64 文本
    upload_payload = {                                                                 ### 上传请求体
        "FileName": filename_on_misty, "Data": b64,
        "ImmediatelyApply": play_now, "OverwriteExisting": overwrite_existing
    }
    upload_url = f"http://{misty_ip}/api/audio"                                        ### 上传端点
    r_up = _post_with_retry(upload_url, upload_payload, timeout_upload_sec)            ### ✅ 带重试上传
    upload_result = r_up.json()                                                        ### 解析上传返回

    play_payload = {"FileName": filename_on_misty, "Volume": volume}                   ### 播放参数
    play_url = f"http://{misty_ip}/api/audio/play"                                     ### 播放端点
    r_play = _post_with_retry(play_url, play_payload, timeout_play_sec)                ### ✅ 带重试播放
    play_result = r_play.json()                                                        ### 解析播放返回

    # ------------------------ 将本次 TTS 结果记录到固定 JSON 文件（mp3=Base64 + duration） -----------
    try:
        _append_tts_json_record(                                                       ### 追加写 {text, emotion, mp3, duration_sec}
            text=text,
            emotion=emotion,
            mp3_b64=b64,
            duration_sec=duration_sec,                                                 ### NEW: 传入准确的时长
            json_file="temp_emotion_speaking_mp3.json",
        )
    except Exception as _e:
        print(f"[WARN] append TTS json record failed: {_e}")

    wait_s = max(0.0, duration_sec + float(fudge_seconds))                             ### 语音长度 + 缓冲

    # —— 自动挑动作（如果未显式传入 action_func 且给了情绪）———————————————
    if action_func is None and emotion in EMOTION_ACTIONS:
        action_func = EMOTION_ACTIONS[emotion]

    action_thread_obj = None
    if action_func is not None:
        ak = dict(action_kwargs or {})
        ak.setdefault("pause_before_reset", wait_s)

        def _run_action():
            try:
                if action_start_offset > 0:
                    time.sleep(action_start_offset)
                action_func(misty_ip, **ak)
            except Exception as e:
                print(f"[WARN] action_func raised: {e}")

        if run_action_in_thread:
            action_thread_obj = threading.Thread(
                target=_run_action, name="misty_action", daemon=True
            )
            action_thread_obj.start()
        else:
            _run_action()

    if block_until_finished:
        if action_thread_obj is not None and join_action_when_block:
            action_thread_obj.join()
        else:
            if wait_s > 0:
                time.sleep(wait_s)

    return {
        "filename_on_misty": filename_on_misty,
        "upload_result": upload_result,
        "play_result": play_result,
        "bytes_len": len(audio_bytes),
        "estimated_duration_sec": duration_sec,
        "response_format": response_format,
        "model": model, "voice": voice,
        "speed": speed, "instructions": instructions,
        "emotion": emotion,
        "canonical_emotion": emotion,
        "action_selected": (getattr(action_func, "__name__", None) if action_func else None),
        "action_started": action_func is not None,
        "action_pause_used_sec": (wait_s if action_func is not None else None),
        "action_start_offset": (action_start_offset if action_func is not None else None),
    }

# ------------------------ 便捷入口：把 emotion 放到最前，零配置即可用 -------------------------------

def _speak_with_emotion(                                                               ### 便捷入口
    openai_api_key: str,
    misty_ip: str,
    emotion: str,
    text: str,
    **overrides,
):
    """最小使用：
    _speak_with_emotion(API_KEY, "192.168.8.157", "兴奋", "太棒了，我们开始吧！")
    """
    canon = _canonical_emotion(emotion)
    action_func = EMOTION_ACTIONS.get(canon)
    return misty_humanlike_speaking(
        openai_api_key=openai_api_key,
        misty_ip=misty_ip,
        text=text,
        emotion=canon,
        action_func=action_func,
        **overrides
    )

# ------------------------ 批处理入口 ---------------------------------------------------------------

def speak_with_emotion(
    openai_api_key: str,
    misty_ip: str,
    items: List[Dict[str, Any]],
    default_voice: str = "coral",
    default_volume: int = 80,
    default_model: str = "gpt-4o-mini-tts",
    default_response_format: str = "mp3",
    default_fudge_seconds: float = 0.5,
    default_action_start_offset: float = 0.0,
    block_until_finished: bool = True,
    gap_seconds: float = 0.0
) -> List[Dict[str, Any]]:
    """ items 每项支持字段：
        - text (必填) / emotion (必填)
        - voice/speed/instructions/volume/model/response_format/fudge_seconds（可选）
        - play_now/overwrite_existing/auto_unique_name/timeout_upload_sec/timeout_play_sec（可选）
        - action_start_offset/run_action_in_thread/join_action_when_block（可选）
        - filename_on_misty（可选）
    """
    try:
        _init_tts_json_file("temp_emotion_speaking_mp3.json")
    except Exception as e:
        print(f"[WARN] init json file failed: {e}")

    results: List[Dict[str, Any]] = []
    assert isinstance(items, list) and items, "items 必须是非空 list[{text, emotion,...}]"

    for idx, it in enumerate(items):
        try:
            assert isinstance(it, dict), f"第 {idx} 项不是 dict"
            text = it.get("text")
            emotion = it.get("emotion")
            assert isinstance(text, str) and text.strip(), f"第 {idx} 项缺少 text"
            assert isinstance(emotion, str) and emotion.strip(), f"第 {idx} 项缺少 emotion"

            voice = it.get("voice", default_voice)
            volume = int(it.get("volume", default_volume))
            model = it.get("model", default_model)
            response_format = it.get("response_format", default_response_format)
            fudge_seconds = float(it.get("fudge_seconds", default_fudge_seconds))
            action_start_offset = float(it.get("action_start_offset", default_action_start_offset))

            kwargs = {
                "voice": voice,
                "volume": volume,
                "model": model,
                "response_format": response_format,
                "fudge_seconds": fudge_seconds,
                "action_start_offset": action_start_offset,
                "play_now": it.get("play_now"),
                "overwrite_existing": it.get("overwrite_existing", True),
                "auto_unique_name": it.get("auto_unique_name", True),
                "timeout_upload_sec": it.get("timeout_upload_sec", 30),
                "timeout_play_sec": it.get("timeout_play_sec", 20),
                "block_until_finished": it.get("block_until_finished", block_until_finished),
                "run_action_in_thread": it.get("run_action_in_thread", True),
                "join_action_when_block": it.get("join_action_when_block", True),
                "filename_on_misty": it.get("filename_on_misty"),
                "speed": it.get("speed"),
                "instructions": it.get("instructions"),
            }

            res = _speak_with_emotion(
                openai_api_key=openai_api_key,
                misty_ip=misty_ip,
                emotion=emotion,
                text=text,
                **{k: v for k, v in kwargs.items() if v is not None}
            )
            res["_index"] = idx
            res["_text"] = text
            results.append(res)

            if block_until_finished and gap_seconds > 0:
                time.sleep(gap_seconds)

        except Exception as e:
            results.append({
                "_index": idx,
                "error": str(e),
                "_item": it,
            })

    return results

# ------------------------ 异步薄封装：给 Agent/上层 await 用 -------------------------------------------

async def misty_humanlike_speaking_async(*args, **kwargs):
    """把同步阻塞实现丢到线程池，不阻塞事件循环，也不创建新的事件循环。"""                    ###
    return await asyncio.to_thread(misty_humanlike_speaking, *args, **kwargs)

async def speak_with_emotion_async(*args, **kwargs):
    """批处理的异步薄封装。"""                                                               ###
    return await asyncio.to_thread(speak_with_emotion, *args, **kwargs)


