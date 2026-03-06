

import os, json, time                                          
from typing import Dict, Any, List, Optional                    

from .Misty_Process_Scheduler import start_worker_bg                       
from .Misty_Process_Tools import read_registry, write_registry      

def rehydrate_from_registry(
    reg_path: str = "misty_proc_registry.json",                
    mode: str = "replace",                                     
    default_api_key: Optional[str] = None                      
) -> Dict[str, Any]:
    """从旧注册表重建所有订阅；返回 {reg_path, backup, results}。"""
    reg_path = os.path.abspath(reg_path)                        
    reg: Dict[str, Any] = read_registry(reg_path)               
    if not reg:                                                 
        return {"reg_path": reg_path, "backup": None, "results": []}

    backup = None                                               

    write_registry({}, reg_path)                                

    results: List[Dict[str, Any]] = []                          
    for key, ent in reg.items():                                
        event_type = ent.get("event_type")                      
        position   = ent.get("position")                        
        ip         = ent.get("ip")                              
        callback   = ent.get("callback")                        
        debounce   = int(ent.get("debounce_ms", 800))           
        keep_alive = bool(ent.get("keep_alive", True))          
        trace      = bool(ent.get("trace", False))              
        api_key    = ent.get("api_key") or default_api_key or os.getenv("MISTY_API_KEY_DEFAULT")  
        log_dir    = os.path.dirname(ent.get("log_path", "./logs")) or "./logs"                   #

        if not (event_type and ip and callback):                
            results.append({"key": key, "status": "skipped", "reason": "missing event_type/ip/callback"})
            continue

        try:
            ret = start_worker_bg(                              
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
                store_api_key=bool(api_key)                     
            )
            results.append({"key": key, **ret})                 
        except Exception as e:
            results.append({"key": key, "status": "error", "error": str(e)})

    return {"reg_path": reg_path, "backup": backup, "results": results}
