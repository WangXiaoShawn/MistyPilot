# -*- coding: utf-8 -*-
# Misty_Process_Worker.py


import os, sys, json, time, traceback                                          ### 基础库
import importlib, importlib.util, inspect                                       ### 动态导入
from random import randint                                                      ### 事件名
from typing import Optional, Callable, Dict, Any, List                           ### typing
from websocket import WebSocketApp, enableTrace                                 ### WS 客户端
import requests                                                                 ### 保持依赖

# -------- 事件与位置 --------
VALID_BUMP_SENSORS = {"bfl", "bfr", "brl", "brr"}                               ### 碰撞
VALID_CAP_SENSORS  = {"Chin", "Scruff", "HeadRight", "HeadLeft", "HeadBack", "HeadFront"}  ### 触摸
AVAILABLE_TYPES    = {"TouchSensor", "BumpSensor"}                               ### 类型

# -------- PubSub 报文工具 --------
def event_filter(name: str, op: str, val: Any) -> Dict[str, Any]:               ### 过滤项
    return {"Property": name, "Inequality": op, "Value": val}                   ### 字典

def _build_subscribe(event_type: str, debounce_ms: int, event_name: str,
                     conditions: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:  ### 订阅体
    msg = {"Operation": "subscribe", "Type": event_type, "DebounceMs": debounce_ms,
           "EventName": event_name, "Message": ""}                               ### 基本
    if conditions: msg["EventConditions"] = conditions                           ### 增加过滤
    return msg                                                                   ### 返回

def _build_unsubscribe(event_name: str) -> Dict[str, Any]:                       ### 退订体
    return {"Operation": "unsubscribe", "EventName": event_name, "Message": ""}  ### 返回

# -------- 回调解析 --------
def _resolve_callback(cb_spec: str) -> Callable:##传递绝对路径比较安全 给一个函数名字返回一个函数                            ### 解析回调
    try:
        mod_part, func_name = cb_spec.rsplit(":", 1)                             ### 拆分
    except ValueError:
        if "." in cb_spec and not cb_spec.endswith(".py"):                       ### 支持 module.func
            mod_part, func_name = cb_spec.rsplit(".", 1)                         ### 拆分
        else:
            raise TypeError("Callback must be 'module:func' or '/path/file.py:func'")  ### 抛错
    if mod_part.endswith(".py") or mod_part.startswith(".") or mod_part.startswith("/"):  ### 路径模式
        path = os.path.abspath(mod_part)                                         ### 绝对路径
        if not os.path.exists(path):                                             ### 存在性校验
            raise ModuleNotFoundError(f"callback file not found: {path}")        ### 抛错
        mod_name = f"_usercb_{abs(hash(path)) & 0xffffffff:x}"                   ### 临时模块名
        spec = importlib.util.spec_from_file_location(mod_name, path)            ### 构建 spec
        if spec is None or spec.loader is None:                                  ### 校验
            raise ImportError(f"cannot load callback module from {path}")        ### 抛错
        mod = importlib.util.module_from_spec(spec)                              ### 创建模块
        sys.modules[mod_name] = mod                                              ### 注册
        spec.loader.exec_module(mod)                                             ### 执行
        fn = getattr(mod, func_name)                                             ### 取函数
        if not callable(fn):                                                     ### 可调用校验
            raise TypeError(f"{cb_spec} is not callable")                        ### 抛错
        return fn                                                                ### 返回
    else:
        mod = importlib.import_module(mod_part)                                  ### 模块导入
        fn  = getattr(mod, func_name)                                            ### 取函数
        if not callable(fn):                                                     ### 校验
            raise TypeError(f"{cb_spec} is not callable")                        ### 抛错
        return fn                                                                ### 返回

def _call_callback(cb: Callable, evt: dict, misty_ip: str, api_key: Optional[str]) -> None:  ### 调用回调
    sig = inspect.signature(cb)                                                         ### 签名
    argc = len(sig.parameters)                                                          ### 形参数
    if argc <= 1: cb(evt)                                                               ### (event)
    elif argc == 2: cb(evt, misty_ip)                                                         ### (event, ip)
    else: cb(evt, misty_ip, api_key)                                                          ### (event, ip, key)

# -------- 订阅实现 --------
def _subscribe_event(ip: str, event_type: str, *, conditions: Optional[List[Dict[str, Any]]],
                     debounce_ms: int, keep_alive: bool, on_event, api_key: Optional[str],
                     trace: bool) -> Dict[str, Any]:
    if event_type not in AVAILABLE_TYPES:                                         ### 类型校验
        raise ValueError(f"Invalid event_type: {event_type}. Allowed: {AVAILABLE_TYPES}")  ### 抛错
    if event_type == "TouchSensor" and conditions:                                ### 触摸位校验
        for cond in conditions:
            if cond.get("Property") == "sensorPosition":
                val = cond.get("Value")
                if val not in VALID_CAP_SENSORS:
                    print(f"[Warn] sensorPosition='{val}' not in {VALID_CAP_SENSORS}")     ### 提示
    event_name = str(randint(0, 10_000_000_000))                                   ### 事件名
    state = {"got_first": False, "keep_alive": bool(keep_alive),
             "event_name": event_name, "on_event": on_event}                       ### 状态
    headers = []                                                                    ### 头
    if api_key: headers.append(f"Authorization: Bearer {api_key}")                 ### 鉴权
    enableTrace(bool(trace))                                                        ### trace
    url = f"ws://{ip}/pubsub"                                                       ### WS 地址

    def _on_open(ws: WebSocketApp):                                                ### 打开时
        ws.send(json.dumps(_build_subscribe(event_type, debounce_ms, event_name, conditions)))  ### 订阅

    def _on_message(ws: WebSocketApp, message: str):                               ### 收到消息
        if not state["got_first"]:                                                 ### 跳 ack
            state["got_first"] = True                                              ### 标记
            return                                                                  ### 返回
        try:
            data = json.loads(message)                                             ### 解析
        except Exception as e:
            print(f"[ERROR] Failed to parse WebSocket message: {e}", file=sys.stderr)  ### 错误日志
            return                                                                  ### 忽略
        try:
            state["on_event"](data)                                                ### 调用回调
        except Exception as e:
            print(f"[ERROR] Callback execution failed: {e}", file=sys.stderr)     ### 错误日志
            traceback.print_exc()                                                  ### 打印堆栈
        if not state["keep_alive"]:                                                ### 单次订阅
            try: ws.send(json.dumps(_build_unsubscribe(state["event_name"])))     ### 退订
            finally: ws.close()                                                   ### 关闭

    def _on_error(ws: WebSocketApp, error):                                        ### 错误
        print(f"[ERROR] WebSocket error: {error}", file=sys.stderr)               ### 错误日志

    def _on_close(ws: WebSocketApp, code, msg):                                    ### 关闭
        pass                                                                        ### 安静

    ws = WebSocketApp(url, header=headers, on_open=_on_open, on_message=_on_message,
                      on_error=_on_error, on_close=_on_close)                      ### 构建
    return {"ws": ws, "event_name": event_name, "keep_alive": state["keep_alive"]} ### 返回句柄

# -------- Worker 主循环 --------
def _worker_main(cfg: Dict[str, Any]) -> None:                                     ### 主入口
    ip        = cfg.get("ip")                                                      ### IP
    api_key   = cfg.get("api_key")                                                 ### KEY
    etype     = cfg.get("event_type")                                              ### 类型
    pos       = cfg.get("position")                                                ### 位置
    cb_spec   = cfg.get("callback")                                                ### 回调说明
    debounce  = int(cfg.get("debounce_ms", 800))                                   ### 去抖
    kalive    = bool(cfg.get("keep_alive", True))                                   ### 常驻
    trace     = bool(cfg.get("trace", False))                                       ### trace

    cb = _resolve_callback(cb_spec)                                                ### 解析回调
    def _on_event(evt: dict) -> None:                                              ### 包装回调
        try: _call_callback(cb, evt, ip, api_key)                                   ### 适配实参
        except Exception: traceback.print_exc()                                     ### 打印

    while True:                                                                     ### 永久循环
        handle = None                                                               ### 句柄
        try:
            conds = None                                                            ### 过滤
            if etype == "TouchSensor" and pos:
                conds = [event_filter("sensorPosition", "=", pos)]
            elif etype == "BumpSensor" and pos:
                conds = [event_filter("sensorId", "=", pos)]
            handle = _subscribe_event(ip, etype, conditions=conds,                  ### 订阅
                                      debounce_ms=debounce, keep_alive=kalive,
                                      on_event=_on_event, api_key=api_key, trace=trace)
            handle["ws"].run_forever(ping_timeout=10)                               ### 阻塞收取
        except KeyboardInterrupt:
            break                                                                    ### 退出
        except Exception:
            traceback.print_exc()                                                   ### 打印
            time.sleep(3.0)                                                         ### 回退
        finally:
            try:
                if handle and handle.get("ws"): handle["ws"].close()               ### 清理
            except Exception:
                pass
            time.sleep(1.0)                                                         ### 歇会儿

                                                        ### 运行

# -------- 进程入口：读取环境变量配置并启动 --------
if __name__ == "__main__":                                                        ### 入口
    cfg_path = os.environ.get("MISTY_WORKER_CFG", "").strip()  # 环境文件也会传进来                    ### 取配置路径
    if not cfg_path or not os.path.exists(cfg_path):                               ### 校验
        print("[FATAL] missing env MISTY_WORKER_CFG or file not found.", file=sys.stderr)  ### 错
        sys.exit(2)                                                                ### 退
    with open(cfg_path, "r", encoding="utf-8") as f:                               ### 读配置
        cfg = json.load(f)                                                         ### 加载
    _worker_main(cfg)       