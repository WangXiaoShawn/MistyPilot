

import os, sys, json, time, signal, subprocess, tempfile                     
from typing import Optional, Dict, Any, List                                   


from .Misty_Process_Tools import (
    _abs_path, _read, _write_atomic, _key,       
    _update_registry_atomic, _delete_registry_key_atomic,  
    is_alive, stop_pid,                        
)

VALID_BUMP_SENSORS = {"bfl", "bfr", "brl", "brr"}                             
VALID_CAP_SENSORS  = {"Chin", "Scruff", "HeadRight", "HeadLeft", "HeadBack", "HeadFront"}  
AVAILABLE_TYPES    = {"TouchSensor", "BumpSensor"}                            

def start_worker_bg(
    *,
    ip: str,                                                                    
    event_type: str,                                                             
    position: Optional[str],                                                     
    callback: str,                                                               
    api_key: Optional[str] = None,                                                
    debounce_ms: int = 800,                                                      
    keep_alive: bool = True,                                                     
    trace: bool = False,                                                          
    mode: str = "reuse",                                                          
    reg_path: Optional[str] = None,                                               
    log_dir: str = "./logs",                                                      
    store_api_key: bool = False                                                 
) -> Dict[str, Any]:
    if event_type not in AVAILABLE_TYPES:
        raise ValueError(f"event_type must be in {AVAILABLE_TYPES}")

    if event_type == "TouchSensor" and position and position not in VALID_CAP_SENSORS:
        raise ValueError(f"Touch position must be in {VALID_CAP_SENSORS}, got '{position}'")

    if event_type == "BumpSensor" and position and position not in VALID_BUMP_SENSORS:
        raise ValueError(f"Bump sensor must be in {VALID_BUMP_SENSORS}, got '{position}'")

    if mode not in {"reuse", "replace", "parallel"}:
        raise ValueError("mode must be one of: reuse|replace|parallel")

    reg_path = _abs_path(reg_path)                                                
    os.makedirs(os.path.dirname(reg_path) or ".", exist_ok=True)                 
    os.makedirs(log_dir, exist_ok=True)                                         
    key = _key(event_type, position)                                            
    reg = _read(reg_path)                                                        
    ent = reg.get(key)                                                           

    if ent and is_alive(int(ent.get("pid", -1))):                               
        if mode == "reuse":                                                      
            return {"status": "reused", "pid": int(ent["pid"]), "key": key, "position": position}
        elif mode == "replace":                                                  
            stop_pid(int(ent["pid"]))                                            
            _delete_registry_key_atomic(reg_path, key)                          
        elif mode == "parallel":                                                
            pass                                                                 
    elif ent:                                                                     
        _delete_registry_key_atomic(reg_path, key)                              

    cfg = {                                                                     
        "ip": ip, "api_key": api_key, "event_type": event_type, "position": position,
        "callback": callback, "debounce_ms": int(debounce_ms),
        "keep_alive": bool(keep_alive), "trace": bool(trace),
    }
    cfg_file = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")     
    json.dump(cfg, cfg_file, ensure_ascii=False, indent=2)                      
    cfg_file.flush()                                                             
    cfg_file_path = cfg_file.name                                                
    cfg_file.close()                                                             

    log_path = os.path.join(log_dir, f"misty_{event_type}_{position or 'ANY'}_error.log")  
    env = os.environ.copy()
    env["MISTY_WORKER_CFG"] = cfg_file_path                                      

    worker_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Misty_Process_Worker.py")  
    if not os.path.exists(worker_py):
        raise FileNotFoundError(f"misty_bg_worker.py not found at {worker_py}")

    out = open(log_path, "a")                                                    
    proc = subprocess.Popen(                                                     
        [sys.executable, worker_py],
        stdout=out, stderr=subprocess.STDOUT, env=env,
        start_new_session=True
    )
    out.close()                                                                   

    entry_data = {                                                               
        "pid": proc.pid, "event_type": event_type, "position": position,
        "ip": ip, "api_key": (api_key if store_api_key else None),
        "callback": callback, "debounce_ms": int(debounce_ms),
        "keep_alive": bool(keep_alive), "trace": bool(trace),
        "started_at": time.time(), "name": f"misty-bg-{event_type}-{position or 'ANY'}",
        "cfg_path": cfg_file_path, "log_path": os.path.abspath(log_path),
    }
    _update_registry_atomic(reg_path, key, entry_data)                           

    return {"status": "started", "pid": proc.pid, "key": key, "position": position}
