

import os, sys, json, time, signal                       ### 基础库
from typing import Optional, Dict, Any, List             ### typing

DEFAULT_REG_PATH = "misty_proc_registry.json"            ### 默认 JSON 路径

# ---------------- 内部工具 ----------------

def _abs_path(path: Optional[str]) -> str:
    """规范化 JSON 路径（优先入参，其次 env:MISTY_REG_PATH，最后 DEFAULT_REG_PATH）。"""
    p = path or os.getenv("MISTY_REG_PATH", DEFAULT_REG_PATH)         ### 选源
    return os.path.abspath(p)                                         ### 转绝对路径

def _read(path: str) -> Dict[str, Any]:
    """读 JSON（失败返回空字典，容错）。"""
    if not os.path.exists(path): return {}                            ### 文件不存在返回空
    try:
        with open(path, "r", encoding="utf-8") as f:                  ### 打开文件
            return json.load(f)                                       ### 解析 JSON
    except Exception:
        return {}                                                     ### 出错容错

def _write_atomic(path: str, data: Dict[str, Any]) -> None:
    """原子写 JSON，避免并发写入产生半文件。"""
    tmp = f"{path}.tmp"                                               ### 临时文件路径
    with open(tmp, "w", encoding="utf-8") as f:                       ### 写临时
        json.dump(data, f, ensure_ascii=False, indent=2)              ### dump JSON
    os.replace(tmp, path)                                             ### 原子替换

def _key(event_type: str, position: Optional[str]) -> str:
    """组合键：Type:Position（Position 为空则 ANY）。"""
    return f"{event_type}:{position or 'ANY'}"                        ### 统一 key 规则

def is_alive(pid: int) -> bool:
    """检测 PID 是否存活（POSIX: os.kill(pid, 0)）。"""
    try:
        os.kill(pid, 0)                                               ### 信号 0 探测
        return True                                                   ### 仍在
    except Exception:
        return False                                                  ### 已死

def stop_pid(pid: int, timeout: float = 5.0) -> bool:
    """优雅停止指定 PID（TERM→等待→KILL）。"""
    try:
        os.kill(pid, signal.SIGTERM)                                  ### 发送 TERM
        t0 = time.time()                                              ### 记录起始时间
        while time.time() - t0 < timeout:                             ### 等待退出
            if not is_alive(pid): return True                         ### 已退出
            time.sleep(0.2)                                           ### 小睡
        try:
            os.kill(pid, signal.SIGKILL)                              ### 超时强杀
        except Exception:
            pass                                                      ### 忽略异常
        return True                                                   ### 视为成功
    except Exception:
        return False                                                  ### 发送信号失败

# ---------------- 公开 API：读/写 ----------------

def read_registry(reg_path: Optional[str] = None) -> Dict[str, Any]:
    """读取注册表（字典形式）。"""
    path = _abs_path(reg_path)                                        ### 规范路径
    return _read(path)                                                ### 读 JSON

def write_registry(reg: Dict[str, Any], reg_path: Optional[str] = None) -> None:
    """覆盖写入注册表（危险操作，通常不需要直接调用）。"""
    path = _abs_path(reg_path)                                        ### 规范路径
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)          ### 确保目录存在
    _write_atomic(path, reg)                                          ### 原子写

# ---------------- 公开 API：查询/控制 ----------------

def list_workers(reg_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    返回所有条目的列表；每条包含：
      - key / pid / alive / event_type / position / name / log_path / ip / api_key / started_at / callback / ...
    未知字段原样透传（如果注册表里有）。
    """
    path = _abs_path(reg_path)                                        ### 规范路径
    data = _read(path)                                                ### 读取
    out: List[Dict[str, Any]] = []                                    ### 结果列表
    for k, v in data.items():                                         ### 遍历条目
        item = dict(v)                                                ### 浅拷贝
        item["key"] = k                                               ### 附带 key
        try:
            item["pid"] = int(v.get("pid", -1))                       ### 规范 pid
        except Exception:
            item["pid"] = -1                                          ### 容错
        item["alive"] = is_alive(item["pid"])                         ### 实时 alive
        # 关键字段兜底
        item.setdefault("event_type", k.split(":", 1)[0])             ### 推断类型
        item.setdefault("position",  None if ":" not in k else k.split(":", 1)[1])  ### 推断位置
        out.append(item)                                              ### 收集
    return out                                                        ### 返回列表

def get_entry(event_type: str, position: Optional[str],
              reg_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """按 (event_type, position) 取条目；不存在返回 None。"""
    key = _key(event_type, position)                                  ### 组合 key
    data = _read(_abs_path(reg_path))                                 ### 读取
    ent = data.get(key)                                               ### 取条目
    if ent is None: return None                                       ### 不存在
    ent2 = dict(ent)                                                  ### 浅拷贝
    ent2["key"] = key                                                 ### 附 key
    ent2["alive"] = is_alive(int(ent.get("pid", -1)))                 ### 附 alive
    return ent2                                                       ### 返回条目

def stop_worker_by_key(event_type: str, position: Optional[str],
                       reg_path: Optional[str] = None) -> bool:
    """按 (event_type, position) 停止并移除；成功/已不存在返回 True，失败 False。"""
    path = _abs_path(reg_path)                                        ### 规范路径
    data = _read(path)                                                ### 读取
    key  = _key(event_type, position)                                 ### 组合 key
    ent  = data.get(key)                                              ### 取条目
    if not ent:                                                       ### 不存在
        # 即使注册表中没有条目，也尝试清理可能的孤儿进程
        cleanup_orphan_workers()                                     ### 清理孤儿进程
        return True                                                   ### 视为已停止
    pid = int(ent.get("pid", -1))                                     ### 取 PID
    ok  = stop_pid(pid)                                               ### 尝试停止
    data.pop(key, None)                                               ### 无论成败都移除条目
    _write_atomic(path, data)                                         ### 写回
    # 停止特定worker后，也清理可能的孤儿进程
    cleanup_orphan_workers()                                         ### 清理孤儿进程
    return ok                                                         ### 返回结果

def stop_worker_by_key_string(key: str, reg_path: Optional[str] = None) -> bool:
    """按 'Type:Pos' 键停止（等价于 stop_worker_by_key 的字符串版）。"""
    if ":" in key:
        etype, pos = key.split(":", 1)                                ### 拆解
        pos = None if pos == "ANY" else pos                           ### 还原 ANY
    else:
        etype, pos = key, None                                        ### 仅类型
    return stop_worker_by_key(etype, pos, reg_path)                   ### 调用主函数

def stop_all_workers(reg_path: Optional[str] = None) -> int:
    """停止全部条目；返回成功发送停止信号的数量（不保证都成功退出）。"""
    path = _abs_path(reg_path)                                        ### 规范路径
    data = _read(path)                                                ### 读取
    count = 0                                                         ### 计数
    for k, ent in list(data.items()):                                 ### 遍历
        try:
            pid = int(ent.get("pid", -1))                             ### 取 PID
            if stop_pid(pid): count += 1                              ### 成功则计数+1
        except Exception:
            pass                                                      ### 忽略
        data.pop(k, None)                                             ### 从表移除
    _write_atomic(path, data)                                         ### 写回
    return count                                                      ### 返回数量

def cleanup_orphan_workers() -> int:
    import subprocess
    import sys
    try:
        # 使用 ps 命令查找所有 Misty_Process_Worker.py 进程
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        orphan_pids = []
        for line in lines:
            if 'Misty_Process_Worker.py' in line and 'python' in line:
                # 提取 PID（第二列）
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        orphan_pids.append(pid)
                    except ValueError:
                        continue
        
        # 停止所有找到的孤儿进程
        stopped_count = 0
        for pid in orphan_pids:
            if stop_pid(pid):
                stopped_count += 1
        
        return stopped_count
    except Exception:
        return 0  # 出错时返回 0

def prune_dead(reg_path: Optional[str] = None) -> int:
    """清理 JSON 中已死亡的 PID 条目；返回删掉的条目数。"""
    path = _abs_path(reg_path)                                        ### 规范路径
    data = _read(path)                                                ### 读取
    removed = 0                                                       ### 计数
    for k, ent in list(data.items()):                                 ### 遍历
        try:
            pid = int(ent.get("pid", -1))                             ### 取 PID
        except Exception:
            pid = -1                                                  ### 容错
        if not is_alive(pid):                                         ### 已死
            data.pop(k, None)                                         ### 移除
            removed += 1                                              ### +1
    _write_atomic(path, data)                                         ### 写回
    return removed                                                    ### 返回数量

# ---------------- 便捷 API：直接用 key 列表进行批量控制 ----------------

def stop_workers_by_keys(keys: List[str], reg_path: Optional[str] = None) -> Dict[str, bool]:
    """按一组 'Type:Pos' 键批量停止；返回 {key: True/False}。"""
    res: Dict[str, bool] = {}                                         ### 结果映射
    for k in keys:                                                    ### 遍历
        res[k] = stop_worker_by_key_string(k, reg_path)               ### 停止并记录
    return res                                                        ### 返回

def list_keys(reg_path: Optional[str] = None) -> List[str]:
    """仅返回所有键的列表（'Type:Pos'）。"""
    data = _read(_abs_path(reg_path))                                 ### 读取
    return list(data.keys())                                          ### 返回 key 列表
