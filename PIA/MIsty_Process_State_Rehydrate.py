# -*- coding: utf-8 -*-
# misty_rehydrate.py — 从注册表安全重建所有 worker
# 依赖：与你现有项目同一环境；要求已提供 misty_bg_api.py / misty_bg_ctl_api.py

import os, json, time                                           ### 基础库
from typing import Dict, Any, List, Optional                    ### typing

from .Misty_Process_Scheduler import start_worker_bg                        ### 你现有的启动函数
from .Misty_Process_Tools import read_registry, write_registry      ### 你现有的读/写注册表工具

def rehydrate_from_registry(
    reg_path: str = "misty_proc_registry.json",                 ### 注册表路径
    mode: str = "replace",                                      ### 'reuse'|'replace'|'parallel'，推荐 'replace'
    default_api_key: Optional[str] = None                       ### 若注册表未存 api_key，可在此统一覆盖
) -> Dict[str, Any]:
    """从旧注册表重建所有订阅；返回 {reg_path, backup, results}。"""
    reg_path = os.path.abspath(reg_path)                        ### 规范路径
    reg: Dict[str, Any] = read_registry(reg_path)               ### 读取旧表
    if not reg:                                                 ### 无内容直接返回
        return {"reg_path": reg_path, "backup": None, "results": []}

    backup = None                                               ### 禁用备份功能

    write_registry({}, reg_path)                                ### 关键：清空注册表，避免错误杀 PID

    results: List[Dict[str, Any]] = []                          ### 收集结果
    for key, ent in reg.items():                                ### 遍历旧配置
        event_type = ent.get("event_type")                      ### 事件类型
        position   = ent.get("position")                        ### 位置(None 表示 ANY)
        ip         = ent.get("ip")                              ### Misty IP
        callback   = ent.get("callback")                        ### 回调路径 '.../cb.py:func'
        debounce   = int(ent.get("debounce_ms", 800))           ### 去抖
        keep_alive = bool(ent.get("keep_alive", True))          ### 常驻
        trace      = bool(ent.get("trace", False))              ### WS trace
        api_key    = ent.get("api_key") or default_api_key or os.getenv("MISTY_API_KEY_DEFAULT")  ### 鉴权
        log_dir    = os.path.dirname(ent.get("log_path", "./logs")) or "./logs"                   ### 日志目录兜底

        if not (event_type and ip and callback):                ### 必要字段校验
            results.append({"key": key, "status": "skipped", "reason": "missing event_type/ip/callback"})
            continue

        try:
            ret = start_worker_bg(                              ### 重建该订阅
                ip=ip,
                event_type=event_type,
                position=position,
                callback=callback,
                api_key=api_key,
                debounce_ms=debounce,
                keep_alive=keep_alive,
                trace=trace,
                mode=mode if mode in {"reuse","replace","parallel"} else "replace",
                reg_path=reg_path,
                log_dir=log_dir,
                store_api_key=bool(api_key)                     ### 有 key 就落盘，便于下次再复活
            )
            results.append({"key": key, **ret})                 ### 记录结果
        except Exception as e:
            results.append({"key": key, "status": "error", "error": str(e)})

    return {"reg_path": reg_path, "backup": backup, "results": results}
