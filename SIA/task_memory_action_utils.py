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
    """
    归档临时 JSON 文件和对应的音频文件夹
    同时更新 JSON 中的 mp3 路径引用
    """
    src_path = ""
    for root, _, files in os.walk(start_dir):
        if SRC_BASENAME in files:
            src_path = os.path.abspath(os.path.join(root, SRC_BASENAME))
            break
    if not src_path:
        print(f"[INFO] not found: {SRC_BASENAME}")
        return None

    # 查找对应的音频文件夹
    src_audio_dir = os.path.splitext(src_path)[0] + "_audio"
    
    dest_dir = os.path.abspath(DEST_DIR)
    os.makedirs(dest_dir, exist_ok=True)

    # 找到下一个可用的编号
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
    
    # 目标文件名和路径
    new_name = f"{DEST_PREFIX}{next_n}{DEST_SUFFIX}"
    dest_path = os.path.join(dest_dir, new_name)
    new_audio_dir_name = f"{DEST_PREFIX}{next_n}_audio"
    dest_audio_dir = os.path.join(dest_dir, new_audio_dir_name)
    
    # 读取 JSON 并更新音频路径
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 更新每条记录的 mp3 路径
        if isinstance(data, list):
            for item in data:
                if "mp3" in item and isinstance(item["mp3"], str):
                    # 从旧路径提取文件名
                    old_mp3_path = item["mp3"]
                    mp3_filename = os.path.basename(old_mp3_path)
                    # 更新为新的相对路径
                    item["mp3"] = os.path.join(DEST_DIR, new_audio_dir_name, mp3_filename)
        
        # 写回更新后的 JSON
        with open(src_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[Archive] Updated {len(data)} mp3 paths in JSON")
    except Exception as e:
        print(f"[WARN] Failed to update JSON paths: {e}")
    
    # 移动 JSON 文件
    shutil.move(src_path, dest_path)
    print(f"[OK] Moved JSON: {SRC_BASENAME} -> {dest_path}")
    
    # 移动音频文件夹（如果存在）
    if os.path.exists(src_audio_dir) and os.path.isdir(src_audio_dir):
        shutil.move(src_audio_dir, dest_audio_dir)
        print(f"[OK] Moved audio folder: {os.path.basename(src_audio_dir)} -> {dest_audio_dir}")
    else:
        print(f"[WARN] Audio folder not found: {src_audio_dir}")

    return dest_path
