# -*- coding: utf-8 -*-
# one_shot_tts_misty.py
# 功能：OpenAI TTS -> 上传到 Misty -> 播放（单函数封装 + 可选阻塞等待，按音频时长+0.5s）

import base64            ### base64 for encode audio to string
import time              ### for sleep / unique filename
import requests          ### requests for Misty REST API
import io                ### BytesIO for mutagen
from typing import Optional, Dict, Any, Tuple  ### typing
from openai import OpenAI  #
import os
import json## OpenAI sync client

def load_config(config_filename="config.json"):
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
MISTY_IP = cfg["misty_ip"]



def misty_humanlike_speaking(                                                           ### one-shot: TTS -> upload to Misty -> play（单函数封装）
    openai_api_key: str,                                                                ### OpenAI API Key（用于TTS）
    misty_ip: str,                                                                      ### Misty 机器人 IP
    text: str,                                                                          ### 要合成的文本
    model: str = "gpt-4o-mini-tts",                                                     ### TTS 模型
    voice: str = "coral",                                                               ### TTS 音色
    instructions: str | None = "Speak in a happy tone, with natural pauses between phrases.",  ### 说话风格
    response_format: str = "mp3",                                                       ### 音频容器：mp3|wav|flac|aac|opus|pcm
    filename_on_misty: str | None = "openai_tts_hello.mp3",                             ### 在 Misty 上保存的文件名
    speed: float | None = 1.0,                                                          ### 合成语速(0.25~4.0)；None=默认
    volume: int = 80,                                                                    ### 播放音量(0~100)
    overwrite_existing: bool = True,                                                    ### 是否覆盖同名文件
    play_now: bool = False,                                                             ### 上传端的 ImmediatelyApply（不是播放）
    auto_unique_name: bool = False,                                                     ### True 时在文件名后追加时间戳
    timeout_upload_sec: int = 60,                                                       ### 上传超时 (增加到60秒)
    timeout_play_sec: int = 120,                                                        ### 播放超时 (增加到120秒，解决吞字问题)
    block_until_finished: bool = True,                                                  ### 是否阻塞直到播完
    fudge_seconds: float = 0.5,                                                         ### 额外缓冲（按“时长+fudge”sleep）
    misty_api_key: str | None = None                                                    ### 可选：给 Misty 反代/鉴权的 Bearer
) -> dict:
    """文字→语音→上传→播放→(可选)等待；仅暴露此函数。返回包含上传/播放结果与估计时长的字典。"""  ### 文档字符串

    # ---------------- 内联依赖（不泄露全局符号） ----------------
    import base64                                                                       ### base64 工具
    import time                                                                         ### 睡眠/时间戳
    import requests                                                                     ### HTTP 请求
    import io                                                                           ### BytesIO 给 mutagen
    from openai import OpenAI                                                           ### OpenAI 客户端

    # ---------------- 内部：MP3 时长估计（优先 mutagen，回退首帧/默认码率） ----------------
    def _synchsafe_to_int(bs: bytes) -> int:                                            ### 解析 ID3v2 synchsafe
        return (bs[0] << 21) | (bs[1] << 14) | (bs[2] << 7) | bs[3]                     ### bit-packed

    def _skip_id3v2(audio_bytes: bytes) -> int:                                         ### 跳过 ID3v2 头，返回偏移
        if len(audio_bytes) >= 10 and audio_bytes[0:3] == b"ID3":                       ### 检查标识
            size = _synchsafe_to_int(audio_bytes[6:10])                                 ### 负载大小
            return 10 + size                                                            ### 头(10) + 负载
        return 0                                                                        ### 无 ID3

    _BITRATE_TABLE = {                                                                  ### 比特率表（kbps）
        3: { 3: [0,32,64,96,128,160,192,224,256,288,320,352,384,416,448,0],
             2: [0,32,48,56,64,80,96,112,128,160,192,224,256,320,384,0],
             1: [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0], },
        2: { 3: [0,32,48,56,64,80,96,112,128,144,160,176,192,224,256,0],
             2: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0],
             1: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0], },
        0: { 3: [0,32,48,56,64,80,96,112,128,144,160,176,192,224,256,0],
             2: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0],
             1: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0], },
    }                                                                                   ### ver_id/layer 索引
    _SAMPLERATE_TABLE = {                                                               ### 采样率（Hz）
        3: [44100, 48000, 32000],                                                       ### MPEG1
        2: [22050, 24000, 16000],                                                       ### MPEG2
        0: [11025, 12000, 8000],                                                        ### MPEG2.5
    }

    def _first_frame_bitrate_samplerate(audio_bytes: bytes) -> tuple[int | None, int | None]:  ### 提取首帧码率/采样率
        off = _skip_id3v2(audio_bytes)                                                         ### 跳过 ID3
        end = min(len(audio_bytes) - 4, off + 4096)                                            ### 扫描窗口
        i = off                                                                                ### 游标
        while i < end:                                                                         ### 扫描同步字
            b0 = audio_bytes[i]                                                                ### 第1字节
            b1 = audio_bytes[i+1]                                                              ### 第2字节
            if b0 == 0xFF and (b1 & 0xE0) == 0xE0:                                             ### 命中 0xFFE
                hdr = int.from_bytes(audio_bytes[i:i+4], "big")                                ### 取头
                ver_id   = (hdr >> 19) & 0b11                                                  ### 版本
                layer    = (hdr >> 17) & 0b11                                                  ### 层
                br_idx   = (hdr >> 12) & 0b1111                                                ### 比特率索引
                sr_idx   = (hdr >> 10) & 0b11                                                  ### 采样率索引
                if ver_id == 1 or layer == 0 or br_idx == 0xF or sr_idx == 0x3:                ### 非法组合
                    i += 1                                                                     ### 继续
                    continue                                                                   ### 下一个
                if ver_id not in _BITRATE_TABLE or layer not in _BITRATE_TABLE[ver_id]:        ### 不支持
                    i += 1                                                                     ### 继续
                    continue                                                                   ### 下一个
                bitrate_kbps = _BITRATE_TABLE[ver_id][layer][br_idx]                           ### kbps
                if bitrate_kbps == 0:                                                          ### free/坏帧
                    i += 1                                                                     ### 继续
                    continue                                                                   ### 下一个
                samplerate = _SAMPLERATE_TABLE.get(ver_id, [None, None, None])[sr_idx]         ### Hz
                if not samplerate:                                                             ### 非法采样率
                    i += 1                                                                     ### 继续
                    continue                                                                   ### 下一个
                return bitrate_kbps, samplerate                                                ### 返回
            i += 1                                                                             ### 向前
        return None, None                                                                      ### 未找到

    def _mp3_duration_seconds(audio_bytes: bytes) -> float:                                    ### MP3 时长估计
        try:
            from mutagen.mp3 import MP3                                                        ### 动态导入
            return MP3(io.BytesIO(audio_bytes)).info.length                                    ### 精确长度
        except Exception:
            pass                                                                               ### 无 mutagen/失败走降级
        id3_skip = _skip_id3v2(audio_bytes)                                                    ### 去掉 ID3
        br_kbps, _ = _first_frame_bitrate_samplerate(audio_bytes)                              ### 首帧码率
        if br_kbps and br_kbps > 0:                                                            ### 有码率
            bits = max(0, (len(audio_bytes) - id3_skip)) * 8                                   ### 负载位数
            return bits / (br_kbps * 1000.0)                                                   ### 秒
        DEFAULT_KBPS = 128                                                                      ### 保守默认
        return (len(audio_bytes) * 8) / (DEFAULT_KBPS * 1000.0)                                 ### 粗估

    # ---------------- 参数与文件名处理 ----------------
    assert response_format in {"mp3","wav","flac","aac","opus","pcm"}, "Invalid response_format"  ### 容器校验
    if not filename_on_misty:                                                                    ### 缺省文件名
        filename_on_misty = f"openai_tts_{int(time.time())}.{response_format}"                   ### 生成
    if auto_unique_name:                                                                         ### 追加时间戳
        base, dot, ext = filename_on_misty.partition(".")                                        ### 分割
        filename_on_misty = f"{base}_{int(time.time())}.{ext or response_format}"                ### 重组

    # ---------------- 1) OpenAI TTS：文本→音频字节 ----------------
    client = OpenAI(api_key=openai_api_key)                                                      ### 初始化客户端
    create_kwargs = { "model": model, "voice": voice, "input": text, "response_format": response_format }  ### 基础参数
    if instructions is not None:                                                                 ### 可选风格
        create_kwargs["instructions"] = instructions                                             ### 添加
    if speed is not None:                                                                        ### 可选语速
        create_kwargs["speed"] = float(speed)                                                    ### 添加
    resp = client.audio.speech.create(**create_kwargs)                                           ### 同步生成
    audio_bytes = resp.read()                                                                    ### 取字节

    # ---------------- 2) 估计时长（仅 mp3 才计算） ----------------
    duration_sec = _mp3_duration_seconds(audio_bytes) if response_format == "mp3" else 0.0       ### 估时长

    # ---------------- 3) 上传到 Misty (/api/audio) ----------------
    b64 = base64.b64encode(audio_bytes).decode("ascii")                                          ### 转 base64
    upload_payload = {                                                                           ### 载荷
        "FileName": filename_on_misty,
        "Data": b64,
        "ImmediatelyApply": bool(play_now),
        "OverwriteExisting": bool(overwrite_existing),
    }
    headers = {}                                                                                 ### HTTP 头
    if misty_api_key:                                                                            ### 可选鉴权
        headers["Authorization"] = f"Bearer {misty_api_key}"                                     ### Bearer
    upload_url = f"http://{misty_ip}/api/audio"                                                  ### 上传端点
    r_up = requests.post(upload_url, json=upload_payload, headers=headers, timeout=timeout_upload_sec)  ### POST
    r_up.raise_for_status()                                                                      ### 非2xx抛错
    upload_result = r_up.json()                                                                  ### 解析返回

    # ---------------- 4) 播放 (/api/audio/play) ----------------
    play_payload = { "FileName": filename_on_misty, "Volume": int(volume) }                      ### 播放参数
    play_url = f"http://{misty_ip}/api/audio/play"                                               ### 播放端点
    r_play = requests.post(play_url, json=play_payload, headers=headers, timeout=timeout_play_sec)  ### POST
    r_play.raise_for_status()                                                                     ### 非2xx抛错
    play_result = r_play.json()                                                                   ### 解析返回

    # ---------------- 5) 可选阻塞等待（时长 + 缓冲） ----------------
    if block_until_finished and duration_sec > 0:                                                 ### 需要等待
        wait_s = max(0.0, float(duration_sec) + float(fudge_seconds))                             ### 计算时长
        time.sleep(wait_s)                                                                         ### 睡眠等待

    # ---------------- 返回结构化结果 ----------------
    return {
        "filename_on_misty": filename_on_misty,                                                   ### 最终文件名
        "upload_result": upload_result,                                                           ### 上传返回
        "play_result": play_result,                                                               ### 播放返回
        "bytes_len": len(audio_bytes),                                                            ### 字节数
        "estimated_duration_sec": duration_sec,                                                   ### 估计时长(秒)
        "response_format": response_format,                                                       ### 音频容器
        "model": model, "voice": voice, "speed": speed, "instructions": instructions             ### TTS 参数回显
    }


