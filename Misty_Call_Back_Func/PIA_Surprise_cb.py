import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from local_audio import play_emotion_sounds
from typing import Optional
from typing import Dict, Any


    
def surprise(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute surprise emotion with sound effects.
    Plays local MP3 in parallel with surprise actions.
    """
    robot = Robot(misty_ip)
    # Sound effect + voice line play in the background (paths are relative to this
    # directory; skipped when use_local_audio is false in MistyPilot_config.json)
    play_emotion_sounds(robot, "surprise.mp3", "excited_surprise_strong.mp3")
    # Perform surprise actions (emotion, LED, movements)
    perform_surprise(misty_ip, api_key)
    
    # Note: Audio plays in background, callback returns immediately
    
    
def cb_surprise(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    WHEN TO USE:
    - User wants Misty to express surprise or shock

    Chinese keywords: 惊讶, 惊喜, 吃惊, 意外, 震惊
    English keywords: surprise, shocked, amazed, astonished, wow
    """
    surprise(misty_ip, api_key)
    
