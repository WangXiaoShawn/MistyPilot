# -*- coding: utf-8 -*-
# Misty_Process_Scheduler.py — 启动/登记后台 worker；控制/注册表逻辑直接使用 m

import os, sys, json, time, signal, subprocess, tempfile                       ### 基础库
from typing import Optional, Dict, Any, List                                    ### typing


from .Misty_Process_Tools import (
    _abs_path, _read, _write_atomic, _key,       ### 工具：路径/读/原子写/组合键
    is_alive, stop_pid,                          ### 工具：存活检测/停止 PID
)

# -------- 常量 & 校验集 --------
VALID_BUMP_SENSORS = {"bfl", "bfr", "brl", "brr"}                               ### 碰撞传感器集合
VALID_CAP_SENSORS  = {"Chin", "Scruff", "HeadRight", "HeadLeft", "HeadBack", "HeadFront"}  ### 触摸传感器集合
AVAILABLE_TYPES    = {"TouchSensor", "BumpSensor"}                               ### 支持的事件类型

# -------- 后台启动：程序式 API --------
def start_worker_bg(
    *,
    ip: str,                                                                      ### Misty IP
    event_type: str,                                                              ### "TouchSensor"/"BumpSensor"
    position: Optional[str],                                                      ### 触摸/碰撞位置，或 None 表示 ANY
    callback: str,                                                                ### 回调：'/abs/file.py:func' 或 'module:func'
    api_key: Optional[str] = None,                                                ### Bearer/None
    debounce_ms: int = 800,                                                       ### 去抖
    keep_alive: bool = True,                                                      ### 持久订阅
    trace: bool = False,                                                          ### WS trace
    mode: str = "reuse",                                                          ### 'reuse'|'replace'|'parallel'
    reg_path: Optional[str] = None,                                               ### JSON 路径
    log_dir: str = "./logs",                                                      ### 日志目录
    store_api_key: bool = False                                                   ### 是否把 api_key 落盘（默认否）
) -> Dict[str, Any]:
    """启动独立后台 worker（父进程立即返回），把 PID 写入 JSON 并返回 {'status','pid','key','position'}。"""
    if event_type not in AVAILABLE_TYPES:
        raise ValueError(f"event_type must be in {AVAILABLE_TYPES}")

    if event_type == "TouchSensor" and position and position not in VALID_CAP_SENSORS:
        raise ValueError(f"Touch position must be in {VALID_CAP_SENSORS}, got '{position}'")

    if event_type == "BumpSensor" and position and position not in VALID_BUMP_SENSORS:
        raise ValueError(f"Bump sensor must be in {VALID_BUMP_SENSORS}, got '{position}'")

    if mode not in {"reuse", "replace", "parallel"}:
        raise ValueError("mode must be one of: reuse|replace|parallel")

    reg_path = _abs_path(reg_path)                                                ### 规范 JSON 路径（支持 env:MISTY_REG_PATH）
    os.makedirs(os.path.dirname(reg_path) or ".", exist_ok=True)                  ### 确保目录存在
    os.makedirs(log_dir, exist_ok=True)                                           ### 确保日志目录存在

    key = _key(event_type, position)                                              ### 组合 key
    reg = _read(reg_path)                                                         ### 读 JSON
    ent = reg.get(key)                                                            ### 旧条目

    if ent and is_alive(int(ent.get("pid", -1))):                                 ### 若旧进程存活
        if mode == "reuse":                                                       ### 复用
            return {"status": "reused", "pid": int(ent["pid"]), "key": key, "position": position}
        elif mode == "replace":                                                   ### 替换
            stop_pid(int(ent["pid"]))                                             ### 停旧
            reg.pop(key, None)                                                    ### 移除旧条目
        elif mode == "parallel":                                                  ### 并行
            pass                                                                  ### 继续起新
    elif ent:                                                                      ### JSON 脏数据
        reg.pop(key, None)                                                        ### 清理

    cfg = {                                                                       ### 构建 worker 配置
        "ip": ip, "api_key": api_key, "event_type": event_type, "position": position,
        "callback": callback, "debounce_ms": int(debounce_ms),
        "keep_alive": bool(keep_alive), "trace": bool(trace),
    }
    cfg_file = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")     ### 建临时配置文件
    json.dump(cfg, cfg_file, ensure_ascii=False, indent=2)                        ### 写配置
    cfg_file.flush()                                                              ### 落盘
    cfg_file_path = cfg_file.name                                                 ### 取路径
    cfg_file.close()                                                              ### 关句柄

    log_path = os.path.join(log_dir, f"misty_{event_type}_{position or 'ANY'}_error.log")  ### 错误日志文件
    env = os.environ.copy()
    env["MISTY_WORKER_CFG"] = cfg_file_path                                       ### 传递配置路径

    worker_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Misty_Process_Worker.py")  ### worker 路径
    if not os.path.exists(worker_py):
        raise FileNotFoundError(f"misty_bg_worker.py not found at {worker_py}")

    out = open(log_path, "a")                                                     ### 打开日志文件
    proc = subprocess.Popen(                                                      ### 启动子进程
        [sys.executable, worker_py],
        stdout=out, stderr=subprocess.STDOUT, env=env,
        start_new_session=True
    )
    out.close()                                                                   ### 父进程关闭句柄

    reg[key] = {                                                                  ### 写 JSON 条目
        "pid": proc.pid, "event_type": event_type, "position": position,
        "ip": ip, "api_key": (api_key if store_api_key else None),
        "callback": callback, "debounce_ms": int(debounce_ms),
        "keep_alive": bool(keep_alive), "trace": bool(trace),
        "started_at": time.time(), "name": f"misty-bg-{event_type}-{position or 'ANY'}",
        "cfg_path": cfg_file_path, "log_path": os.path.abspath(log_path),
    }
    _write_atomic(reg_path, reg)                                                  ### 原子写回

    return {"status": "started", "pid": proc.pid, "key": key, "position": position}
