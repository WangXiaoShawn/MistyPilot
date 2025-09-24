# task_memory_utils.py
import os
import re
import json
import shutil
from datetime import datetime
from typing import Optional

SRC_BASENAME = "temp_emotion_speaking_mp3.json"
DEST_DIR = "emotion_action_speaking_memory"
DEST_PREFIX = "emotion_action_speaking_"
DEST_SUFFIX = ".json"
PREV_TASK_JSON_PATH = "./prev_task.json"

def save_prev_task(task_text: str) -> None:
    data = {
        "prev_task": task_text,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(PREV_TASK_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[INFO] prev task saved -> {PREV_TASK_JSON_PATH}")

def load_prev_task() -> Optional[str]:
    if not os.path.exists(PREV_TASK_JSON_PATH):
        return None
    try:
        with open(PREV_TASK_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("prev_task")
    except Exception as e:
        print(f"[WARN] load_prev_task failed: {e}")
        return None

def archive_temp_mp3_json(start_dir: str = ".") -> Optional[str]:
    src_path = ""
    for root, _, files in os.walk(start_dir):
        if SRC_BASENAME in files:
            src_path = os.path.abspath(os.path.join(root, SRC_BASENAME))
            break
    if not src_path:
        print(f"[INFO] not found: {SRC_BASENAME}")
        return None

    dest_dir = os.path.abspath(DEST_DIR)
    os.makedirs(dest_dir, exist_ok=True)

    pattern = re.compile(rf"^{re.escape(DEST_PREFIX)}(\d+){re.escape(DEST_SUFFIX)}$")
    max_n = 0
    for name in os.listdir(dest_dir):
        m = pattern.match(name)
        if m:
            try:
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    next_n = max_n + 1
    new_name = f"{DEST_PREFIX}{next_n}{DEST_SUFFIX}"
    dest_path = os.path.join(dest_dir, new_name)
    shutil.move(src_path, dest_path)

    print(f"[OK] moved {SRC_BASENAME} -> {dest_path}")
    return dest_path
