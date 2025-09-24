# -*- coding: utf-8 -*-                                                             ### file encoding
# mp3_json_player_only_audio_b64.py                                                 ### filename

import base64                                                                        ### base64 encode/decode
import os                                                                            ### path utils (for local file)
import time                                                                          ### sleep / timestamp
import io                                                                            ### BytesIO for mutagen
from typing import Optional, Dict, Any, Tuple, List                                  ### typing
import requests                                                                      ### HTTP for Misty REST
import json                                                                          ### json utils

def misty_play_json_mp3(                                                                 ### 单一公开函数：按含 audio_b64 的 JSON/列表，在 Misty 上上传并播放 MP3
    misty_ip: str,                                                                       ### 必填：Misty 机器人 IP
    items=None,                                                                          ### 可选：列表[List[Dict]]，每项至少含 {"audio_b64": "..."}；可与 json_path 二选一
    json_path: str | None = None,                                                        ### 可选：JSON 文件路径（内容等价于 items）
    default_volume: int = 80,                                                            ### 默认音量 0-100
    default_fudge_seconds: float = 0.5,                                                  ### 每段音频播放后额外等待的尾部缓冲秒数
    block_until_finished: bool = True,                                                   ### True：顺序阻塞等待每段播完；False：不等待
    gap_seconds: float = 0.0,                                                            ### 段间间隔（仅在阻塞模式且非最后一段生效）
    overwrite_existing: bool = True,                                                     ### 覆盖已存在同名文件
    auto_unique_name: bool = True,                                                       ### 自动在文件名后拼接时间戳保证唯一
    timeout_upload_sec: int = 60,                                                        ### 上传接口超时秒 (增加到60秒)
    timeout_play_sec: int = 120,                                                         ### 播放接口超时秒 (增加到120秒，解决吞字问题)
    api_key: str | None = None                                                           ### 可选：反代/鉴权用 Bearer Token
) -> list[dict]:                                                                         ### 返回：每段的执行结果/错误字典列表
    import base64                                                                        ### 内联依赖：base64
    import io                                                                            ### 内联依赖：字节流
    import json                                                                          ### 内联依赖：JSON 解析
    import time                                                                          ### 内联依赖：休眠/时间戳
    import requests                                                                      ### 内联依赖：HTTP 请求
    from typing import Optional, Dict, Any, Tuple, List                                  ### 类型标注（可选）

    # -------------------------- 内部小工具：全部定义在函数体内，避免对外泄露 --------------------------

    def _load_items_from_json(_json_path: str) -> List[Dict[str, Any]]:                  ### 从文件读取 items
        with open(_json_path, "r", encoding="utf-8") as f:                               ### 打开文件
            return json.load(f)                                                          ### 解析 JSON

    def _synchsafe_to_int(bs: bytes) -> int:                                             ### 解析 ID3v2 synchsafe 整数
        return (bs[0] << 21) | (bs[1] << 14) | (bs[2] << 7) | bs[3]                      ### 位拼接

    def _skip_id3v2(audio_bytes: bytes) -> int:                                          ### 跳过 ID3v2 头部，返回偏移
        if len(audio_bytes) >= 10 and audio_bytes[0:3] == b"ID3":                        ### 判断是否有 ID3v2
            size = _synchsafe_to_int(audio_bytes[6:10])                                  ### 取 payload 大小
            return 10 + size                                                             ### 头 10B + payload
        return 0                                                                         ### 无 ID3v2

    _BITRATE_TABLE = {                                                                   ### 比特率表（kbps）
        3: { 3: [0,32,64,96,128,160,192,224,256,288,320,352,384,416,448,0],
             2: [0,32,48,56,64,80,96,112,128,160,192,224,256,320,384,0],
             1: [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0], },
        2: { 3: [0,32,48,56,64,80,96,112,128,144,160,176,192,224,256,0],
             2: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0],
             1: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0], },
        0: { 3: [0,32,48,56,64,80,96,112,128,144,160,176,192,224,256,0],
             2: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0],
             1: [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160,0], },
    }                                                                                     ### 以 ver_id/layer 索引
    _SAMPLERATE_TABLE = {                                                                 ### 采样率表（Hz）
        3: [44100, 48000, 32000],                                                         ### MPEG1
        2: [22050, 24000, 16000],                                                         ### MPEG2
        0: [11025, 12000, 8000],                                                          ### MPEG2.5
    }

    def _first_frame_bitrate_samplerate(audio_bytes: bytes) -> Tuple[Optional[int], Optional[int]]:  ### 粗提取首帧码率/采样率
        off = _skip_id3v2(audio_bytes)                                                   ### 跳过 ID3v2
        end = min(len(audio_bytes) - 4, off + 4096)                                      ### 限定扫描窗口
        i = off                                                                          ### 初始化游标
        while i < end:                                                                   ### 线性扫描
            b0 = audio_bytes[i]                                                          ### 第 1 字节
            b1 = audio_bytes[i+1]                                                        ### 第 2 字节
            if b0 == 0xFF and (b1 & 0xE0) == 0xE0:                                       ### 0xFFE 同步字
                hdr = int.from_bytes(audio_bytes[i:i+4], "big")                          ### 4B 头转 int
                ver_id   = (hdr >> 19) & 0b11                                            ### 版本位
                layer    = (hdr >> 17) & 0b11                                            ### 层位
                br_idx   = (hdr >> 12) & 0b1111                                          ### 比特率索引
                sr_idx   = (hdr >> 10) & 0b11                                            ### 采样率索引
                if ver_id == 1 or layer == 0 or br_idx == 0xF or sr_idx == 0x3:          ### 非法组合
                    i += 1                                                               ### 前进一步
                    continue                                                             ### 继续找
                bitrate_kbps = _BITRATE_TABLE[ver_id][layer][br_idx]                     ### 查码率
                if bitrate_kbps == 0:                                                    ### 自由/坏帧
                    i += 1                                                               ### 前进一步
                    continue                                                             ### 继续找
                samplerate = _SAMPLERATE_TABLE.get(ver_id, [None, None, None])[sr_idx]   ### 查采样率
                if not samplerate:                                                       ### 非法采样率
                    i += 1                                                               ### 前进一步
                    continue                                                             ### 继续找
                return bitrate_kbps, samplerate                                          ### 命中返回
            i += 1                                                                       ### 继续扫描
        return None, None                                                                ### 未找到

    def _mp3_duration_seconds(audio_bytes: bytes) -> float:                              ### 估计 MP3 时长（优先 mutagen）
        try:
            from mutagen.mp3 import MP3                                                  ### 动态导入 mutagen
            return MP3(io.BytesIO(audio_bytes)).info.length                              ### 精确时长
        except Exception:
            pass                                                                         ### 无 mutagen 或失败则走回退
        id3_skip = _skip_id3v2(audio_bytes)                                              ### 去掉 ID3 头
        br_kbps, _ = _first_frame_bitrate_samplerate(audio_bytes)                        ### 首帧估码率
        if br_kbps and br_kbps > 0:                                                      ### 有可靠码率
            bits = max(0, (len(audio_bytes) - id3_skip)) * 8                             ### 仅计算音频负载
            return bits / (br_kbps * 1000.0)                                             ### CBR 估计
        DEFAULT_KBPS = 128                                                               ### 无法识别时的缺省码率
        return (len(audio_bytes) * 8) / (DEFAULT_KBPS * 1000.0)                          ### 粗估

    def _decode_audio_b64_to_bytes(audio_b64: str) -> bytes:                             ### 将 audio_b64（含 data:URL 也可）解码为字节
        assert isinstance(audio_b64, str) and audio_b64.strip(), "audio_b64 不能为空"       ### 校验
        s = audio_b64.strip()                                                            ### 去空白
        if s.startswith("data:audio/"):                                                  ### 处理 data:URL
            comma = s.find(",")                                                          ### 查逗号分隔
            assert comma > 0, "无效的 data: URL"                                          ### 校验
            s = s[comma+1:].strip()                                                      ### 取逗号后数据
        s += "=" * (-len(s) % 4)                                                         ### 补齐 base64 padding
        return base64.b64decode(s)                                                       ### 真正解码

    def _slug(text: str, max_len: int = 40) -> str:                                      ### 基于文本生成安全文件名
        base = "".join(ch if ch.isalnum() else "_" for ch in (text or ""))               ### 仅保留字母数字与下划线
        base = "_".join(filter(None, base.split("_")))                                   ### 折叠连续下划线
        return (base[:max_len] or "clip")                                                ### 截断并兜底

    def _upload_mp3_to_misty(
        mp3_bytes: bytes,                                                                ### 要上传的字节
        filename_on_misty: str | None,                                                   ### 目标文件名
        play_now: bool = False                                                           ### 是否立即应用（此处我们分步：先传后播，故默认 False）
    ) -> Dict[str, Any]:
        nonlocal api_key, timeout_upload_sec, overwrite_existing, misty_ip               ### 使用外层参数
        if not filename_on_misty:                                                        ### 空名则生成
            filename_on_misty = f"mp3_{int(time.time())}.mp3"                            ### 时间戳命名
        headers = {}                                                                     ### HTTP 头
        if api_key:                                                                      ### 可选鉴权
            headers["Authorization"] = f"Bearer {api_key}"                               ### Bearer
        url = f"http://{misty_ip}/api/audio"                                             ### 上传接口

        # A 方案：JSON+base64                                                                ###
        try:
            b64 = base64.b64encode(mp3_bytes).decode("ascii")                            ### 转 base64 文本
            payload = {                                                                  ### 组装 JSON
                "FileName": filename_on_misty,
                "Data": b64,
                "ImmediatelyApply": play_now,
                "OverwriteExisting": overwrite_existing
            }
            r = requests.post(url, json=payload, headers=headers, timeout=timeout_upload_sec)  ### 发送
            if r.status_code // 100 == 2:                                                ### 2xx 成功
                return {"mode": "json_base64", "filename_on_misty": filename_on_misty, "result": r.json()}  ### 返回
            err_a = f"{r.status_code} {r.text[:200]}"                                    ### 记录错误
        except Exception as e:
            err_a = f"{type(e).__name__}: {e}"                                           ### 异常文本

        # B 方案：multipart/form-data                                                          ###
        files = {"file": (filename_on_misty, io.BytesIO(mp3_bytes), "audio/mpeg")}       ### 表单文件
        try:
            r2 = requests.post(url, files=files, headers=headers, timeout=timeout_upload_sec)  ### 发送
            r2.raise_for_status()                                                        ### 非 2xx 抛错
            return {"mode": "multipart", "filename_on_misty": filename_on_misty, "result": r2.json(), "fallback_from": err_a}  ### 返回
        except Exception as e2:
            raise RuntimeError(f"上传失败；A(JSON)错误：{err_a}；B(multipart)错误：{type(e2).__name__}: {e2}")  ### 双路均失败

    def _play_on_misty(filename_on_misty: str, volume: int) -> Dict[str, Any]:           ### 触发播放
        nonlocal api_key, timeout_play_sec, misty_ip                                     ### 使用外层参数
        payload = {"FileName": filename_on_misty, "Volume": int(volume)}                 ### 播放参数
        headers = {}                                                                     ### HTTP 头
        if api_key:                                                                      ### 可选鉴权
            headers["Authorization"] = f"Bearer {api_key}"                               ### Bearer
        url = f"http://{misty_ip}/api/audio/play"                                        ### 播放接口
        r = requests.post(url, json=payload, headers=headers, timeout=timeout_play_sec)  ### POST 调用
        r.raise_for_status()                                                             ### 非 2xx 抛错
        return r.json()                                                                  ### 返回结果

    # -------------------------- 参数准备与校验 -----------------------------------------------------

    if items is None:                                                                    ### 未直接给 items
        assert isinstance(json_path, str) and json_path.strip(), "必须提供 json_path 或 items"   ### 至少其一
        items = _load_items_from_json(json_path)                                         ### 从文件载入
    assert isinstance(items, list) and len(items) > 0, "items 必须是非空 list"             ### 列表非空

    results: list[dict] = []                                                             ### 收集每段结果

    # -------------------------- 主循环：逐段上传→播放→可选等待 ------------------------------------

    for idx, it in enumerate(items):                                                     ### 遍历每一项
        try:
            assert isinstance(it, dict), f"第 {idx} 项不是 dict"                            ### 类型校验
            text = (it.get("text") or "").strip()                                        ### 可选文本（仅用于命名）
            audio_b64 = it.get("audio_b64")                                              ### 必填：音频 base64
            assert isinstance(audio_b64, str) and audio_b64.strip(), f"第 {idx} 项缺少 audio_b64"  ### 校验存在

            volume = int(it.get("volume", default_volume))                               ### 取音量
            fudge_seconds = float(it.get("fudge_seconds", default_fudge_seconds))        ### 尾部缓冲

            mp3_bytes = _decode_audio_b64_to_bytes(audio_b64)                            ### 解码得到字节
            duration_sec = _mp3_duration_seconds(mp3_bytes)                              ### 估计时长
            wait_s = max(0.0, duration_sec + fudge_seconds)                              ### 播放等待时间

            filename_on_misty = (it.get("filename_on_misty") or "").strip()              ### 指定/自动文件名
            if not filename_on_misty:                                                    ### 未指定时
                prefix = _slug(text or "clip")                                           ### 基于文本的前缀
                ts = int(time.time()) if auto_unique_name else 0                         ### 可选时间戳
                filename_on_misty = f"{prefix}_{ts}.mp3" if ts else f"{prefix}.mp3"      ### 构造文件名

            up = _upload_mp3_to_misty(                                                   ### 上传音频文件
                mp3_bytes=mp3_bytes,
                filename_on_misty=filename_on_misty,
                play_now=False
            )

            play_result = _play_on_misty(                                                ### 触发播放
                filename_on_misty=filename_on_misty,
                volume=volume
            )

            if block_until_finished and wait_s > 0:                                      ### 需要阻塞等待
                time.sleep(wait_s)                                                       ### 睡眠等待

            results.append({                                                             ### 记录成功
                "_index": idx,
                "_text": text,
                "filename_on_misty": filename_on_misty,
                "bytes_len": len(mp3_bytes),
                "estimated_duration_sec": duration_sec,
                "upload_result": up,
                "play_result": play_result
            })

            if block_until_finished and idx < len(items) - 1 and gap_seconds > 0:        ### 段间间隔
                time.sleep(gap_seconds)                                                  ### 间隔等待

        except Exception as e:                                                           ### 本段失败
            results.append({"_index": idx, "error": str(e), "_item": it})               ### 记录错误

    return results                                              ### return all
