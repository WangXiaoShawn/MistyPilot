# -*- coding: utf-8 -*-
import time, base64, pathlib, typing, requests

REMOTE_NAME = "misty_temp_record.wav"   # 远端与本地统一文件名

# --- 小工具：大小写不敏感取值（Misty 有时返回 Status/Result/… 大小写不一） ---
def _ci_get(d: dict, *keys, default=None):
    if not isinstance(d, dict):
        return default
    lower = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        v = lower.get(str(k).lower())
        if v is not None:
            return v
    return default

def _list_audio_names(misty_ip: str) -> typing.List[str]:
    r = requests.get(f"http://{misty_ip}/api/audio/list", timeout=10)
    r.raise_for_status()
    items = _ci_get(r.json(), "result") or []
    out = []
    for it in items:
        nm = _ci_get(it, "name", "Name")
        if isinstance(nm, str):
            out.append(nm)
    return out

# ===== 1) 开始录音（固定名：misty_temp_record.wav） =====
def start_misty_recording(misty_ip: str) -> str:
    # 停掉潜在冲突服务（忽略报错）
    for ep in ("/api/avstreaming/stop", "/api/audio/keyphrase/stop"):
        try:
            requests.post(f"http://{misty_ip}{ep}", timeout=5)
        except Exception:
            pass

    r = requests.post(
        f"http://{misty_ip}/api/audio/record/start",
        json={"FileName": REMOTE_NAME},
        timeout=10
    )
    r.raise_for_status()
    if (_ci_get(r.json() or {}, "status", default="").lower() != "success"):
        raise RuntimeError(f"start failed: {r.text}")
    return REMOTE_NAME

# ===== 2) 停止录音 =====
def stop_misty_recording(misty_ip: str) -> None:
    r = requests.post(f"http://{misty_ip}/api/audio/record/stop", timeout=10)
    r.raise_for_status()
    st = _ci_get(r.json() or {}, "status")
    if st and st.lower() != "success":
        raise RuntimeError(f"stop not success: {r.text}")

# ===== 3) 下载到本地（固定名：misty_temp_record.wav） =====
def download_misty_recording(
    misty_ip: str,
    save_dir: typing.Union[str, pathlib.Path],
    max_wait_sec: float = 30.0
) -> pathlib.Path:
    save_dir = pathlib.Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 轮询等待远端文件出现（有的机子停录后一小段时间才可见）
    deadline = time.time() + max_wait_sec
    want = REMOTE_NAME.lower()
    found = None
    while time.time() < deadline:
        names = _list_audio_names(misty_ip)
        for nm in names:
            if nm.lower() == want:
                found = nm
                break
        if found:
            break
        time.sleep(0.5)

    if not found:
        raise FileNotFoundError(f"remote audio not found: {REMOTE_NAME}")

    # 以 Base64 拉取
    r = requests.get(
        f"http://{misty_ip}/api/audio",
        params={"FileName": found, "Base64": "true"},
        timeout=30
    )
    r.raise_for_status()
    res = _ci_get(r.json(), "result") or r.json()
    b64 = _ci_get(res, "base64", "Base64")
    if not b64:
        raise RuntimeError("no base64 in response")

    raw = base64.b64decode(b64)
    out_path = save_dir / REMOTE_NAME
    out_path.write_bytes(raw)
    return out_path

# ===== 用法 =====
if __name__ == "__main__":
    # start_misty_recording("67.20.196.128")
    stop_misty_recording("67.20.196.128")
    # p = download_misty_recording("67.20.196.128", "./records")

