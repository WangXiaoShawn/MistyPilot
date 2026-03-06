# -*- coding: utf-8 -*-
# Misty_Callback_Executor.py - Execute callback functions directly (for OneTimeCall feature)

import os
import sys
import json
import importlib.util
from typing import Optional, Dict, Any, Callable


def load_config(config_filename="MistyPilot_config.json"):
    """Load configuration file"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "..", config_filename)
    config_path = os.path.abspath(config_path)
    
    with open(config_path, "r") as f:
        return json.load(f)


def resolve_callback_from_spec(cb_spec: str) -> Callable:
    """
    Parse callback function specification and return callable function object
    Supports formats: '/abs/path/file.py:func' or 'module:func'
    """
    try:
        mod_part, func_name = cb_spec.rsplit(":", 1)
    except ValueError:
        raise TypeError("Callback spec must be 'module:func' or '/path/file.py:func'")
    
    # If it's a file path
    if mod_part.endswith(".py") or mod_part.startswith(".") or mod_part.startswith("/"):
        path = os.path.abspath(mod_part)
        if not os.path.exists(path):
            raise ModuleNotFoundError(f"Callback file not found: {path}")
        
        mod_name = f"_testcb_{abs(hash(path)) & 0xffffffff:x}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load callback module from {path}")
        
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        fn = getattr(mod, func_name)
    else:
        # If it's a module name
        mod = importlib.import_module(mod_part)
        fn = getattr(mod, func_name)
    
    if not callable(fn):
        raise TypeError(f"{cb_spec} is not callable")
    
    return fn


def execute_callback_direct(
    callback_spec: str,
    event_data: Optional[Dict[str, Any]] = None,
    misty_ip: Optional[str] = None,
    api_key: Optional[str] = None
) -> Any:
    """
    Execute callback function directly
    
    :param callback_spec: Callback function specification, format 'path/to/file.py:function_name'
    :param event_data: Event data dictionary (if None, creates an empty dictionary)
    :param misty_ip: Misty IP address (loaded from config file, or manually specified)
    :param api_key: API key (optional)
    :return: Return value of the callback function
    """
    # Load configuration
    cfg = load_config()
    if misty_ip is None:
        misty_ip = cfg.get("misty_ip", "127.0.0.1")
    
    # Prepare event data
    if event_data is None:
        event_data = {}
    
    # Parse and load callback function
    print(f"[Executor] Loading callback: {callback_spec}")
    callback_fn = resolve_callback_from_spec(callback_spec)
    
    # Check function signature and call
    import inspect
    sig = inspect.signature(callback_fn)
    argc = len(sig.parameters)
    
    print(f"[Executor] Executing callback with {argc} parameters...")
    print(f"[Executor] Event data: {event_data}")
    print(f"[Executor] Misty IP: {misty_ip}")
    
    if argc <= 1:
        result = callback_fn(event_data)
    elif argc == 2:
        result = callback_fn(event_data, misty_ip)
    else:
        result = callback_fn(event_data, misty_ip, api_key)
    
    print(f"[Executor] Callback executed successfully!")
    return result


def execute_from_cb_summary(
    callback_file_name: str,
    event_data: Optional[Dict[str, Any]] = None,
    misty_ip: Optional[str] = None,
    api_key: Optional[str] = None,
    cb_summary_path: Optional[str] = None
) -> Any:
    """
    Read and execute callback function from cb_functions_summary.json
    This is the core function for MistySensorAgent OneTimeCall feature
    
    :param callback_file_name: Key in cb_functions_summary.json (e.g., 'PIA_Happy_cb.py')
    :param event_data: Event data for simulation
    :param misty_ip: Misty IP address
    :param api_key: API key
    :param cb_summary_path: Path to cb_functions_summary.json (optional, loaded from config by default)
    :return: Return value of the callback function
    """
    # Load configuration
    cfg = load_config()
    if cb_summary_path is None:
        cb_summary_path = cfg.get("CB_SUMMARY_JSON_dir", "cb_functions_summary.json")
    
    # Read cb_functions_summary.json
    if not os.path.exists(cb_summary_path):
        raise FileNotFoundError(f"CB summary file not found: {cb_summary_path}")
    
    with open(cb_summary_path, "r", encoding="utf-8") as f:
        cb_summary = json.load(f)
    
    # Find callback function
    if callback_file_name not in cb_summary:
        raise KeyError(f"Callback '{callback_file_name}' not found in {cb_summary_path}")
    
    cb_info = cb_summary[callback_file_name]
    if "error" in cb_info:
        raise ValueError(f"Callback has error: {cb_info['error']}")
    
    callback_spec = cb_info["cb_func"]
    print(f"[Executor] Found callback spec: {callback_spec}")
    if "docs" in cb_info and cb_info["docs"]:
        print(f"[Executor] Docs: {cb_info['docs']}")
    
    # Execute callback
    return execute_callback_direct(callback_spec, event_data, misty_ip, api_key)
