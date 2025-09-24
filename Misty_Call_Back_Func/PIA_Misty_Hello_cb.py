import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from PIA_Misty_Speak_JSON_file import misty_play_json_mp3
from typing import Optional
from typing import Dict, Any
import threading

def misty_hello(misty_ip: str, api_key: Optional[str] = None) -> None:
    t1 = threading.Thread(target=perform_wave_once_right, args=(misty_ip, api_key))
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "P2_Speaking_JSON", "happy_hello.json")
    t2 = threading.Thread(
        target=misty_play_json_mp3,
        kwargs={"misty_ip": misty_ip, "json_path": json_path},
    )
    t1.start()
    t2.start()
    t1.join()
    t2.join()

def cb_hello(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Trigger Misty to express 'hello' or greeting.
    Call this for any user request related to showing greeting, introduction, or welcome
    """
    misty_hello(misty_ip, api_key)
    
