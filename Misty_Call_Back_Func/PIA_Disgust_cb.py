import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_disgust
from PIA_Misty_Speak_JSON_file import misty_play_json_mp3
from typing import Optional
from typing import Dict, Any
import threading

    
def disgust(misty_ip: str, api_key: Optional[str] = None) -> None:
    perform_disgust(misty_ip, api_key)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "P2_Speaking_JSON", "disgust.json")
    misty_play_json_mp3(misty_ip=misty_ip, json_path=json_path)
      
def cb_disgust(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Trigger Misty to express 'disgust' or discomfort.
    Call this for any user request related to showing dislike, rejection, or unease
    
    """
    disgust(misty_ip, api_key)
    