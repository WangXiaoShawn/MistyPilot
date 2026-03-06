# -*- coding: utf-8 -*-
import json
import os

THINKING_STATE_FILE = "thinking_model_power.json"   ### 你的json文件名，确保存在 {"model_power": "low"} 这样的结构

def _load_config_default_model():
    """从配置文件加载默认基础模型"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "MistyPilot_config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("llm_model", "gpt-5-nano")
    except Exception:
        return "gpt-5-nano"  # 最终兜底

def load_thinking_model_power(default_power: str = None) -> str:
    if default_power is None:
        default_power = _load_config_default_model()
    
    if not os.path.exists(THINKING_STATE_FILE):
        data = {"model_power": default_power}
        with open(THINKING_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return default_power

    with open(THINKING_STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("model_power", default_power)
def update_thinking_model_power(new_power: str) -> None:
    data = {"model_power": new_power}
    with open(THINKING_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[UPDATED] model_power -> {new_power}")
def reset_thinking_model_power(default_power: str ) -> None:
    update_thinking_model_power(default_power)
    print(f"[RESET] model_power 已恢复为 '{default_power}'")

