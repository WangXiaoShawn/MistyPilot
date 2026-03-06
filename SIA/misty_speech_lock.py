import json
import time
import os
import threading

LOCK_FILE = "misty_speech_lock.json"
_local_lock = threading.Lock()

def _load_lock_data() -> dict:
    if not os.path.exists(LOCK_FILE):
        return {}
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_lock_data(data: dict):
    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[WARN] Failed to save speech lock: {e}")

def wait_for_speech_lock(buffer: float = 0.1):
    """
    Checks if speech is active and waits if so.
    Blocks until the lock is free (timestamp expired).
    """
    while True:
        # Check lock file
        with _local_lock:
            data = _load_lock_data()
            speaking_until = data.get("speaking_until", 0)
        
        now = time.time()
        remaining = speaking_until - now
        
        if remaining <= 0:
            return # Free to speak
            
        # Wait for a bit, then check again
        # Don't sleep the whole 'remaining' because the file might change (though unlikely to shorten)
        # But we want to be responsive if it expires.
        sleep_time = min(remaining, 0.5) 
        if sleep_time > 0:
            time.sleep(sleep_time)

def acquire_speech_lock(duration_sec: float):
    """
    Sets the lock for the given duration from now.
    """
    with _local_lock:
        data = _load_lock_data()
        now = time.time()
        data["speaking_until"] = now + duration_sec
        _save_lock_data(data)
