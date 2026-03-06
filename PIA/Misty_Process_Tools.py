
import os, sys, json, time, signal                       
import fcntl                                              
from typing import Optional, Dict, Any, List            

DEFAULT_REG_PATH = "misty_proc_registry.json"            


def _abs_path(path: Optional[str]) -> str:
    p = path or os.getenv("MISTY_REG_PATH", DEFAULT_REG_PATH)         
    return os.path.abspath(p)                                        

def _read(path: str) -> Dict[str, Any]:
    if not os.path.exists(path): return {}                           
    
    lock_path = f"{path}.lock"
    lock_file = None
    
    try:
        lock_file = open(lock_path, 'a')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_SH)                
        
        try:
            with open(path, "r", encoding="utf-8") as f:             
                data = json.load(f)                                   
            return data
        except Exception:
            return {}                                                
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)            
            
    except Exception:
        return {}
    finally:
        if lock_file:
            try:
                lock_file.close()
            except:
                pass

def _write_atomic(path: str, data: Dict[str, Any]) -> None:
    lock_path = f"{path}.lock"                                            
    
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    
    for attempt in range(3):
        lock_file = None
        try:
            lock_file = open(lock_path, 'a')                              
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)                
            
            tmp = f"{path}.tmp"                                           
            with open(tmp, "w", encoding="utf-8") as f:                  
                json.dump(data, f, ensure_ascii=False, indent=2)         
            os.replace(tmp, path)                                         
            
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)               
            lock_file.close()
            return
            
        except (FileNotFoundError, OSError) as e:
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except:
                    pass
            
            if attempt < 2:
                time.sleep(0.05 * (attempt + 1))                          
                continue
            else:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return
                except Exception as final_e:
                    raise RuntimeError(f"Failed to write {path} after 3 attempts: {final_e}")
        
        except Exception as e:
            # 其他异常
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except:
                    pass
            
            if attempt == 2:
                raise RuntimeError(f"Failed to write {path}: {e}")
            time.sleep(0.05 * (attempt + 1))
    
    try:
        tmp = f"{path}.tmp"
        if os.path.exists(tmp):
            os.remove(tmp)
    except:
        pass

def _update_registry_atomic(path: str, key: str, value: Dict[str, Any]) -> None:
    lock_path = f"{path}.lock"
    
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    
    for attempt in range(3):
        lock_file = None
        try:
            lock_file = open(lock_path, 'a')
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except:
                    data = {}
            
            data[key] = value
            
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            return
            
        except Exception as e:
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except:
                    pass
            
            if attempt == 2:
                raise RuntimeError(f"Failed to update {path}[{key}]: {e}")
            time.sleep(0.05 * (attempt + 1))

def _delete_registry_key_atomic(path: str, key: str) -> bool:
    lock_path = f"{path}.lock"
    
    for attempt in range(3):
        lock_file = None
        try:
            lock_file = open(lock_path, 'a')
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except:
                    data = {}
            
            # 删除
            existed = key in data
            if existed:
                data.pop(key, None)
                
                # 写入
                tmp = f"{path}.tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmp, path)
            
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            return existed
            
        except Exception as e:
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except:
                    pass
            
            if attempt == 2:
                raise RuntimeError(f"Failed to delete {path}[{key}]: {e}")
            time.sleep(0.05 * (attempt + 1))
    
    return False

def _key(event_type: str, position: Optional[str]) -> str:
    return f"{event_type}:{position or 'ANY'}"                        

def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)                                               
        return True                                                   
    except Exception:
        return False                                                 

def stop_pid(pid: int, timeout: float = 5.0) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)                                  
        t0 = time.time()                                             
        while time.time() - t0 < timeout:                             
            if not is_alive(pid): return True                        
            time.sleep(0.2)                                           
        try:
            os.kill(pid, signal.SIGKILL)                             
        except Exception:
            pass                                                     
        return True                                                   
    except Exception:
        return False                                                 


def read_registry(reg_path: Optional[str] = None) -> Dict[str, Any]:
    path = _abs_path(reg_path)                                        
    return _read(path)                                                

def write_registry(reg: Dict[str, Any], reg_path: Optional[str] = None) -> None:
    path = _abs_path(reg_path)                                        
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)          
    _write_atomic(path, reg)                                          


def list_workers(reg_path: Optional[str] = None) -> List[Dict[str, Any]]:
    
    path = _abs_path(reg_path)                                        
    data = _read(path)                                                
    out: List[Dict[str, Any]] = []                                   
    for k, v in data.items():                                         
        item = dict(v)                                                #
        item["key"] = k                                               
        try:
            item["pid"] = int(v.get("pid", -1))                      
        except Exception:
            item["pid"] = -1                                          
        item["alive"] = is_alive(item["pid"])                         
        item.setdefault("event_type", k.split(":", 1)[0])             
        item.setdefault("position",  None if ":" not in k else k.split(":", 1)[1])  
        out.append(item)                                             
    return out                                                        

def get_entry(event_type: str, position: Optional[str],
              reg_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    key = _key(event_type, position)                                 
    data = _read(_abs_path(reg_path))                                 
    ent = data.get(key)                                               
    if ent is None: return None                                       
    ent2 = dict(ent)                                                  
    ent2["key"] = key                                                 
    ent2["alive"] = is_alive(int(ent.get("pid", -1)))                
    return ent2                                                       

def stop_worker_by_key(event_type: str, position: Optional[str],
                       reg_path: Optional[str] = None) -> bool:
    path = _abs_path(reg_path)                                       
    data = _read(path)                                               
    key  = _key(event_type, position)                                 
    ent  = data.get(key)                                              
    if not ent:                                                       
        cleanup_orphan_workers()                                     
        return True                                                  
    pid = int(ent.get("pid", -1))                                    
    ok  = stop_pid(pid)                                               
    data.pop(key, None)                                               
    _write_atomic(path, data)                                        
    cleanup_orphan_workers()                                         
    return ok                                                         

def stop_worker_by_key_string(key: str, reg_path: Optional[str] = None) -> bool:
    if ":" in key:
        etype, pos = key.split(":", 1)                                
        pos = None if pos == "ANY" else pos                          
    else:
        etype, pos = key, None                                        
    return stop_worker_by_key(etype, pos, reg_path)                 

def stop_all_workers(reg_path: Optional[str] = None) -> int:
    path = _abs_path(reg_path)                                        
    data = _read(path)                                                
    count = 0                                                        
    for k, ent in list(data.items()):                               
        try:
            pid = int(ent.get("pid", -1))                             
            if stop_pid(pid): count += 1                              
        except Exception:
            pass                                                     
        data.pop(k, None)                                             
    _write_atomic(path, data)                                         
    return count                                                      

def cleanup_orphan_workers() -> int:
    import subprocess
    import sys
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        orphan_pids = []
        for line in lines:
            if 'Misty_Process_Worker.py' in line and 'python' in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        orphan_pids.append(pid)
                    except ValueError:
                        continue
        
        stopped_count = 0
        for pid in orphan_pids:
            if stop_pid(pid):
                stopped_count += 1
        
        return stopped_count
    except Exception:
        return 0  

def prune_dead(reg_path: Optional[str] = None) -> int:
    path = _abs_path(reg_path)                                       
    data = _read(path)                                                
    removed = 0                                                       
    for k, ent in list(data.items()):                               
        try:
            pid = int(ent.get("pid", -1))                           
        except Exception:
            pid = -1                                                  
        if not is_alive(pid):                                        
            data.pop(k, None)                                       
            removed += 1                                             
    _write_atomic(path, data)                                         
    return removed                                                    


def stop_workers_by_keys(keys: List[str], reg_path: Optional[str] = None) -> Dict[str, bool]:
    res: Dict[str, bool] = {}                                         
    for k in keys:                                                    
        res[k] = stop_worker_by_key_string(k, reg_path)               
    return res                                                       

def list_keys(reg_path: Optional[str] = None) -> List[str]:
    data = _read(_abs_path(reg_path))                                 
    return list(data.keys())                                         
