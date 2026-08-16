import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from local_audio import play_emotion_sounds
from typing import Optional
from typing import Dict, Any


    
def sad(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute sad emotion with sound effects.
    Plays local MP3 in parallel with sad actions.
    """
    robot = Robot(misty_ip)
    # Sound effect + voice line play in the background (paths are relative to this
    # directory; skipped when use_local_audio is false in MistyPilot_config.json)
    play_emotion_sounds(robot, "crying-said.mp3", "sad_lonely_heavy.mp3")
    # Perform sad actions (emotion, LED, movements)
    perform_sad(misty_ip, api_key)
    
    # Note: Audio plays in background, callback returns immediately
    
def cb_sad(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    WHEN TO USE:
    - User wants Misty to express sadness or grief (emotion/facial expression, NOT music)

    Chinese keywords: 伤心, 难过, 悲伤, 沮丧, 失落
    English keywords: sad, sadness, grief, unhappy, sorrowful
    """
    sad(misty_ip, api_key)
    