# -*- coding: utf-8 -*-                                                             ### file encoding
# mp3_only_player.py (LOCAL AUDIO ONLY VERSION)                                     ### filename

import base64                                                                        ### base64 encode/decode
import os                                                                            ### path utils (for local file)
import time                                                                          ### sleep / timestamp
import io                                                                            ### BytesIO for mutagen
import threading                                                                     ### action threading
from typing import Optional, Dict, Any, Tuple, List, Union, Callable                 ### typing
import json                                                                          ### json utils
from .misty_speech_lock import wait_for_speech_lock, acquire_speech_lock             ### speech locking

# ===== 你的动作函数（保持原样） ===============================================================
from .emotion_actions import (                                                        ### import your action funcs
    perform_arousal_action,          ### Arousal
    perform_excitement_action,       ### Excitement
    perform_sleepiness_action,       ### Sleepiness
    perform_misery_action,           ### Misery
    perform_distress_action,         ### Distress
    perform_pleasure_action,         ### Pleasure
    perform_contentment_action,      ### Contentment
    perform_depression_action,       ### Depression
    perform_neutral_action,          ### Neutral
)

# ===== 情绪到动作映射（仅供播放阶段挑选动作） ===================================================
EMOTION_ACTIONS: Dict[str, Callable[..., None]] = {                                  ### emotion -> action func
    "Arousal":      perform_arousal_action,
    "Excitement":   perform_excitement_action,
    "Distress":     perform_distress_action,
    "Pleasure":     perform_pleasure_action,
    "Contentment":  perform_contentment_action,
    "Sleepiness":   perform_sleepiness_action,
    "Depression":   perform_depression_action,
    "Misery":       perform_misery_action,
    "Neutral":      perform_neutral_action,
}

# 别名到规范情绪名                                                                     
_EMOTION_ALIASES: Dict[str, str] = {                                                 ### aliases -> canonical
    "arousal":"Arousal", "激动":"Arousal", "亢奋":"Arousal",
    "excitement":"Excitement", "兴奋":"Excitement", "喜悦":"Excitement",
    "distress":"Distress", "焦虑":"Distress", "焦灼":"Distress", "苦恼":"Distress",
    "pleasure":"Pleasure", "愉快":"Pleasure",
    "contentment":"Contentment", "满足":"Contentment", "安逸":"Contentment",
    "sleepiness":"Sleepiness", "困倦":"Sleepiness", "犯困":"Sleepiness", "想睡":"Sleepiness",
    "depression":"Depression", "抑郁":"Depression", "低落":"Depression",
    "misery":"Misery", "痛苦":"Misery",
    "neutral":"Neutral", "中立":"Neutral", "平静":"Neutral", "冷静":"Neutral",
}
def load_items_from_json(json_path: str) -> List[Dict[str, Any]]:                     ### load json
    with open(json_path, "r", encoding="utf-8") as f:                                ### open file
        return json.load(f)                                                          ### parse json


def _canonical_emotion(e: Optional[str]) -> Optional[str]:                           ### normalize emotion
    if not e:                                                                        ### empty -> None
        return None                                                                  ### no emotion
    if e in EMOTION_ACTIONS:                                                         ### already canonical
        return e                                                                     ### return as-is
    key = e.strip().casefold()                                                       ### trim+lower
    return _EMOTION_ALIASES.get(key, e)                                              ### alias or original

# ===== MP3 时长估计工具（优先 mutagen，不在则首帧/缺省码率回退） ================================
def _synchsafe_to_int(bs: bytes) -> int:                                             ### parse ID3v2 synchsafe
    return (bs[0] << 21) | (bs[1] << 14) | (bs[2] << 7) | bs[3]                      ### packed bits

def _skip_id3v2(audio_bytes: bytes) -> int:                                          ### skip ID3v2 header
    if len(audio_bytes) >= 10 and audio_bytes[0:3] == b"ID3":                        ### ID3 tag check
        size = _synchsafe_to_int(audio_bytes[6:10])                                  ### payload size
        return 10 + size                                                             ### header(10B)+payload
    return 0     ### no ID3

_BITRATE_TABLE = {                                                                   ### bitrate table (kbps)
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

_SAMPLERATE_TABLE = {                                                                ### sample rate (Hz)
    3: [44100, 48000, 32000],                                                        ### MPEG1
    2: [22050, 24000, 16000],                                                        ### MPEG2
    0: [11025, 12000, 8000],                                                         ### MPEG2.5
}

def _first_frame_bitrate_samplerate(audio_bytes: bytes) -> Tuple[Optional[int], Optional[int]]:
    off = _skip_id3v2(audio_bytes)                                                   ### start offset
    end = min(len(audio_bytes) - 4, off + 4096)                                      ### scan window
    i = off                                                                          ### cursor
    while i < end:                                                                   ### scan
        b0 = audio_bytes[i]                                                          ### byte 0
        b1 = audio_bytes[i+1]                                                        ### byte 1
        if b0 == 0xFF and (b1 & 0xE0) == 0xE0:                                       ### 0xFFE sync
            hdr = int.from_bytes(audio_bytes[i:i+4], "big")                          ### 4B header
            ver_id   = (hdr >> 19) & 0b11                                            ### version id
            layer    = (hdr >> 17) & 0b11                                            ### layer idx
            br_idx   = (hdr >> 12) & 0b1111                                          ### bitrate idx
            sr_idx   = (hdr >> 10) & 0b11                                            ### samplerate idx
            if ver_id == 1 or layer == 0 or br_idx == 0xF or sr_idx == 0x3:          ### invalid
                i += 1                                                               ### step
                continue                                                             ### skip
            bitrate_kbps = _BITRATE_TABLE[ver_id][layer][br_idx]                     ### kbps
            if bitrate_kbps == 0:                                                    ### free/bad
                i += 1                                                               ### step
                continue                                                             ### skip
            samplerate = _SAMPLERATE_TABLE.get(ver_id, [None, None, None])[sr_idx]   ### Hz
            if not samplerate:                                                       ### invalid
                i += 1                                                               ### step
                continue                                                             ### skip
            return bitrate_kbps, samplerate                                          ### ok
        i += 1                                                                       ### next
    return None, None                                                                ### not found

def _mp3_duration_seconds(audio_bytes: bytes) -> float:                               ### seconds estimate
    try:                                                                             ### try mutagen
        from mutagen.mp3 import MP3                                                  ### import
        return MP3(io.BytesIO(audio_bytes)).info.length                              ### accurate
    except Exception:                                                                ### fallback
        pass                                                                         ### ignore
    id3_skip = _skip_id3v2(audio_bytes)                                              ### skip ID3
    br_kbps, _ = _first_frame_bitrate_samplerate(audio_bytes)                        ### first frame
    if br_kbps and br_kbps > 0:                                                      ### have bitrate
        bits = max(0, (len(audio_bytes) - id3_skip)) * 8                             ### payload bits
        return bits / (br_kbps * 1000.0)                                             ### CBR approx
    DEFAULT_KBPS = 128                                                               ### default kbps
    return (len(audio_bytes) * 8) / (DEFAULT_KBPS * 1000.0)                          ### coarse estimate

# ===== MP3 输入归一化：path/base64/bytes (本地播放版，不支持URL) ================================================
def _coerce_mp3_bytes(mp3: Union[str, bytes, bytearray]) -> bytes:                    ### normalize to bytes
    if isinstance(mp3, (bytes, bytearray)):                                          ### already bytes
        return bytes(mp3)                                                            ### return
    assert isinstance(mp3, str) and mp3.strip(), "mp3 必须是 bytes 或非空字符串"       ### sanity check
    s = mp3.strip()                                                                  ### trim
    if s.startswith("data:audio/"):                                                  ### data URL
        comma = s.find(",")                                                          ### find comma
        assert comma > 0, "无效的 data: URL"                                          ### validate
        b64 = s[comma+1:]                                                            ### base64 part
        return base64.b64decode(b64)                                                 ### decode
    if os.path.isfile(s):                                                            ### local file
        with open(s, "rb") as f:                                                     ### open
            return f.read()                                                          ### read
    return base64.b64decode(s)                                                       ### assume raw base64

def _slug(s: str, max_len: int = 40) -> str:                                         ### safe filename
    base = "".join(ch if ch.isalnum() else "_" for ch in s)                          ### alnum/_ only
    base = "_".join(filter(None, base.split("_")))                                   ### collapse _
    return (base[:max_len] or "clip")                                                ### limit len

# ===== 本地播放（只支持电脑扬声器播放）============================================================================

def _play_audio_locally_sync(audio_bytes: bytes) -> bool:
    """
    在本地电脑播放音频（使用 afplay - 最可靠的 macOS 方案）
    
    关键改进：
    1. 完全抛弃 simpleaudio（避免 wait_done() 死锁问题）
    2. 直接使用 macOS 原生 afplay 命令
    3. subprocess.run() 自带超时保护和阻塞等待
    4. 不使用 pydub/ffmpeg，避免进程泄漏
    """
    import subprocess
    import tempfile
    
    try:
        # 直接写入临时文件（不使用 pydub 处理，避免 ffmpeg 进程泄漏）
        with tempfile.NamedTemporaryFile(
            suffix=".mp3", 
            delete=False,
            mode='wb'
        ) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        # 使用 afplay 播放（会阻塞直到播放完成）
        result = subprocess.run(
            ['afplay', tmp_path],
            timeout=40,  # 40秒超时（正常单句音频<15秒，留足安全边际）
            capture_output=True,
            text=True,
            check=False  # 不自动抛出异常，手动检查返回码
        )
        
        # 检查播放结果
        if result.returncode != 0:
            print(f"[afplay] Warning: exit code {result.returncode}")
            if result.stderr:
                print(f"[afplay] stderr: {result.stderr.strip()}")
        
        # 额外等待一小段时间，确保音频缓冲区完全清空
        time.sleep(0.15)
        
        # 删除临时文件
        try:
            os.unlink(tmp_path)
        except Exception as unlink_err:
            print(f"[WARN] Failed to delete temp file: {unlink_err}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired as timeout_err:
        print(f"[ERROR] afplay timeout after 40s: {timeout_err}")
        # 尝试清理临时文件
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        return False
        
    except FileNotFoundError:
        print(f"[ERROR] afplay command not found - are you on macOS?")
        return False
        
    except Exception as e:
        print(f"[ERROR] afplay playback failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ===== 对外主接口：MP3-only 批量播放（本地播放版，支持动作并行、间隔、阻塞/非阻塞） ==============================
def fast_thinking_emotion_speech(                                                    ### batch play (MP3 only, LOCAL)
    misty_ip: str,                                                                   ### Misty IP (for actions only)
    items: Optional[List[Dict[str, Any]]] = None,                                    ### audio items list
    json_path: Optional[str] = None,                                                 ### JSON file path
    default_fudge_seconds: float = 0.8,                                              ### tail buffer
    default_action_start_offset: float = 0.0,                                        ### action delay
    block_until_finished: bool = True,                                               ### block per item
    gap_seconds: float = 0.0,                                                        ### gap between items
    run_action_in_thread: bool = True,                                               ### run action in thread
    join_action_when_block: bool = True                                              ### join action thread
) -> List[Dict[str, Any]]:
    """
    批量播放MP3音频（本地播放版）
    
    特性:
        - 音频在电脑扬声器播放
        - 动作在Misty机器人执行
        - 不支持Misty音频播放
    """
    if items is None:                                                                ### 若未传 items
        assert isinstance(json_path, str) and json_path.strip(), "必须提供 json_path 或 items"
        items = load_items_from_json(json_path)                                      ### 内部加载 JSON

    assert isinstance(items, list) and items, "items 必须是非空 list"                   ### 校验
    
    # 按 index 字段排序，确保播放顺序正确
    items = sorted(items, key=lambda x: x.get("index", 0))
    print(f"[Fast Thinking - Local Audio] Playing {len(items)} items (sorted by index)")
    
    results: List[Dict[str, Any]] = []                                               ### collect
    for idx, it in enumerate(items):                                                 ### iterate items
        try:                                                                         ### guard per item
            assert isinstance(it, dict), f"第 {idx} 项不是 dict"                        ### type check
            text = it.get("text", "")                                                ### optional text
            emotion_raw = it.get("emotion")                                          ### emotion required
            mp3_in = it.get("mp3")                                                   ### mp3 required
            assert isinstance(emotion_raw, str) and emotion_raw.strip(), f"第 {idx} 项缺少 emotion"  ### check
            assert mp3_in is not None, f"第 {idx} 项缺少 mp3"                           ### check

            emotion = _canonical_emotion(emotion_raw)                                 ### normalize emotion
            action_func = EMOTION_ACTIONS.get(emotion)                                ### select action
            fudge_seconds = float(it.get("fudge_seconds", default_fudge_seconds))     ### tail buffer
            action_start_offset = max(0.0, float(it.get("action_start_offset",
                                                        default_action_start_offset)))### action delay

            mp3_bytes = _coerce_mp3_bytes(mp3_in)                                     ### to bytes
            
            # --- 优先使用 JSON 中保存的准确时长（slow thinking生成时记录的） ---
            duration_sec = it.get("duration_sec")                                     ### 尝试从 JSON 获取准确时长
            if duration_sec is None:                                                  ### 若 JSON 中没有
                duration_sec = _mp3_duration_seconds(mp3_bytes)                       ### 回退到估算（兼容旧数据）
                print(f"[WARN] No duration_sec in JSON, using estimated: {duration_sec:.2f}s")  ### 告警
            else:
                print(f"[INFO] Using accurate duration from JSON: {duration_sec:.2f}s")  ### 使用准确时长
            
            # --- 增加缓冲时间，防止时长估算不准导致抢话 ---
            safety_margin = duration_sec * 0.1                                        ### 10% safety margin for VBR
            wait_s = max(0.0, duration_sec + fudge_seconds + safety_margin)           ### audio+buffers

            # --- 本地播放（唯一模式） ---
            print(f"[Player] Item {idx}: Playing locally - {text[:50]}...")
            
            # 防止抢话：等待当前语音结束
            wait_for_speech_lock()
            # 占锁
            acquire_speech_lock(wait_s)
            
            # 在后台线程播放
            play_success = False
            def _play_worker():
                nonlocal play_success
                play_success = _play_audio_locally_sync(mp3_bytes)
            
            play_thread = threading.Thread(target=_play_worker, name=f"local_play_{idx}", daemon=False)  # 改为非守护线程
            play_thread.start()

            # --- 启动Misty动作线程（与音频播放并行） ---
            action_thread_obj = None                                                  ### thread handle
            if action_func is not None:                                               ### action exist
                ak = dict(it.get("action_kwargs", {}))                                ### action kwargs
                ak.setdefault("pause_before_reset", wait_s)                           ### pause by duration

                def _run_action():                                                    ### action runner
                    try:                                                              ### guard
                        if action_start_offset > 0:                                    ### delay
                            time.sleep(action_start_offset)                            ### sleep
                        action_func(misty_ip, **ak)                                   ### call action
                    except Exception as e:                                            ### catch
                        print(f"[WARN] action_func raised: {e}")                      ### warn

                if run_action_in_thread:                                              ### threaded
                    action_thread_obj = threading.Thread(
                        target=_run_action, name=f"misty_action_{idx}", daemon=True   ### daemon thread
                    )
                    action_thread_obj.start()                                         ### start
                else:
                    _run_action()                                                     ### sync

            # --- 等待播放和动作完成 ---
            if block_until_finished:                                                  ### block mode
                if play_thread is not None:                                           ### wait audio
                    play_thread.join()                                                ### wait play end
                if action_thread_obj is not None and join_action_when_block:          ### join action thread
                    action_thread_obj.join()                                          ### wait action end

            results.append({                                                          ### record ok
                "_index": idx, "_text": text, "emotion": emotion,
                "playback_mode": "local",                                             ### 固定本地播放
                "playback_success": play_success,                                     ### 播放是否成功
                "bytes_len": len(mp3_bytes),
                "estimated_duration_sec": duration_sec,
                "action_selected": (getattr(action_func, "__name__", None) if action_func else None),
                "action_started": action_func is not None,
                "action_pause_used_sec": (wait_s if action_func is not None else None),
                "action_start_offset": (action_start_offset if action_func is not None else None),
            })                                                                        ### append result

            if block_until_finished and idx < len(items) - 1 and gap_seconds > 0:     ### inter-item gap
                time.sleep(gap_seconds)                                              ### gap sleep

        except Exception as e:                                                        ### per-item error
            results.append({"_index": idx, "error": str(e), "_item": it})            ### record error
            # continue                                                                ### keep going
    return results                                                                    ### return all

