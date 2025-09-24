import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from PIA_Misty_Speak_JSON_file import misty_play_json_mp3
from typing import Optional
from typing import Dict, Any
import threading


def fear(misty_ip: str, api_key: Optional[str] = None) -> None:
    perform_fear(misty_ip, api_key)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "P2_Speaking_JSON", "fear.json")
    misty_play_json_mp3(misty_ip=misty_ip, json_path=json_path)
    
    
def cb_fear(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Trigger Misty to express 'fear' or discomfort.
    Call this for any user request related to showing fear, anxiety, or unease
    """
    fear(misty_ip, api_key)
    
