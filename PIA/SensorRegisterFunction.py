# -*- coding: utf-8 -*-
import os, json, random, threading, sys
import string
from typing import List, Tuple, Optional, Dict, Any
from typing import List, Optional, Tuple, Annotated

from .Misty_Process_Scheduler import start_worker_bg
from .Misty_Process_Tools import stop_all_workers, stop_worker_by_key, cleanup_orphan_workers

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Misty_Call_Back_Func'))
from CUBS_Misty_Only_Raw_Actions import Robot

_ACK_WORDS = ["Sure.", "OK.", "Alright.", "Done."]

def _speak_ack(ip: str) -> None:
    """Speak a random acknowledgement word in a background thread."""
    def _do():
        try:
            Robot(ip).speak(text=random.choice(_ACK_WORDS), flush=True)
        except Exception:
            pass
    threading.Thread(target=_do, daemon=True).start()

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
MISTY_IP = cfg["misty_ip"]
REG_PATH = cfg["reg_path"]
LOG_DIR = cfg["log_dir"]
CB_SUMMARY_JSON = cfg["CB_SUMMARY_JSON_dir"]

# --- Valid sets for event validation ---
VALID_BUMP_SENSORS = {"bfl", "bfr", "brl", "brr"}  # bump sensors
VALID_CAP_SENSORS = {"Chin", "Scruff", "HeadRight", "HeadLeft", "HeadBack", "HeadFront"}  # capacitive sensors
AVAILABLE_TYPES = {"TouchSensor", "BumpSensor", "OneTimeCall"}


def _load_cb_summary(json_path: str = CB_SUMMARY_JSON) -> Dict[str, Any]:
    """Load cb_functions_summary.json mapping file."""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Callback summary file not found: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def manage_misty_sensor_tasks(
    tasks: Annotated[
        List[
            Tuple[
                Annotated[str, "action, one of {ADD, DELETE_ONE, DELETE_ALL}"],
                Annotated[Optional[str], "event_type, BumpSensor or TouchSensor"],
                Annotated[Optional[str], "position (bfl, bfr, brl, brr, Chin, Scruff, HeadRight, HeadLeft, HeadBack, HeadFront)"],
                Annotated[Optional[str], "callback_file_name"]
            ]
        ],
        "List of tasks, each task is a 4-tuple (action, event_type, position, callback_file_name)"
    ]
) -> List[Dict[str, Any]]:
    
    ip: str = MISTY_IP
    reg_path: str = REG_PATH
    log_dir: str = LOG_DIR

    # Load callback mapping
    cb_summary = _load_cb_summary()
    available_cb_keys = list(cb_summary.keys())

    # -------- Pre-check all tasks --------
    for action, event_type, position, callback_file_name in tasks:
        if action not in {"ADD", "DELETE_ONE", "DELETE_ALL"}:
            return [{
                "status": "error",
                "reason": f"Unknown action: {action}",
                "expected": ["ADD", "DELETE_ONE", "DELETE_ALL"]
            }]

        if action == "ADD":
            if not (event_type and position and callback_file_name):
                return [{
                    "status": "error",
                    "reason": "ADD missing required parameters",
                    "expected": {
                        "event_type": list(AVAILABLE_TYPES),
                        "position": {
                            "BumpSensor": list(VALID_BUMP_SENSORS),
                            "TouchSensor": list(VALID_CAP_SENSORS)
                        },
                        "callback_file_name": available_cb_keys
                    }
                }]
            if event_type not in AVAILABLE_TYPES:
                return [{
                    "status": "error",
                    "reason": f"Invalid event_type: {event_type}",
                    "expected": list(AVAILABLE_TYPES)
                }]
            if event_type == "BumpSensor" and position not in VALID_BUMP_SENSORS:
                return [{
                    "status": "error",
                    "reason": f"Invalid BumpSensor position: {position}",
                    "expected": list(VALID_BUMP_SENSORS)
                }]
            if event_type == "TouchSensor" and position not in VALID_CAP_SENSORS:
                return [{
                    "status": "error",
                    "reason": f"Invalid TouchSensor position: {position}",
                    "expected": list(VALID_CAP_SENSORS)
                }]
            if callback_file_name not in cb_summary:
                return [{
                    "status": "error",
                    "reason": f"Callback file not found in cb_functions_summary.json: {callback_file_name}",
                    "expected": available_cb_keys
                }]

        if action == "DELETE_ONE":
            if not event_type:
                return [{
                    "status": "error",
                    "reason": "DELETE_ONE missing event_type",
                    "expected": list(AVAILABLE_TYPES)
                }]
            if event_type not in AVAILABLE_TYPES:
                return [{
                    "status": "error",
                    "reason": f"Invalid event_type: {event_type}",
                    "expected": list(AVAILABLE_TYPES)
                }]
            if event_type == "BumpSensor" and position not in VALID_BUMP_SENSORS:
                return [{
                    "status": "error",
                    "reason": f"Invalid BumpSensor position: {position}",
                    "expected": list(VALID_BUMP_SENSORS)
                }]
            if event_type == "TouchSensor" and position not in VALID_CAP_SENSORS:
                return [{
                    "status": "error",
                    "reason": f"Invalid TouchSensor position: {position}",
                    "expected": list(VALID_CAP_SENSORS)
                }]
       
    # -------- Execute tasks (safe after validation) --------
    results = []
    for action, event_type, position, callback_file_name in tasks:
        if action == "ADD":
            callback_spec = cb_summary[callback_file_name]["cb_func"]
            ret = start_worker_bg(
                ip=ip,
                event_type=event_type,
                position=position,
                callback=callback_spec,
                mode="replace",
                reg_path=reg_path,
                log_dir=log_dir,
            )
            results.append({"action": "ADD", "status": "success", "result": ret})
            _speak_ack(ip)

        elif action == "DELETE_ONE":
            ok = stop_worker_by_key(event_type=event_type, position=position, reg_path=reg_path)
            results.append({
                "action": "DELETE_ONE",
                "status": "success",
                "event_type": event_type,
                "position": position,
                "stopped": ok
            })
            _speak_ack(ip)

        elif action == "DELETE_ALL":
            # 先停止注册表中的进程
            count = stop_all_workers(reg_path=reg_path)
            # 再清理可能的孤儿进程
            orphan_count = cleanup_orphan_workers()
            total_count = count + orphan_count
            results.append({
                "action": "DELETE_ALL", 
                "status": "success", 
                "stopped_count": count,
                "orphan_count": orphan_count,
                "total_stopped": total_count
            })
            _speak_ack(ip)

    return results
