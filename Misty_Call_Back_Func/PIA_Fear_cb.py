import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from local_audio import play_emotion_sounds
from typing import Optional
from typing import Dict, Any


def fear(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute fear emotion with sound effects.
    Plays local MP3 in parallel with fear actions.
    """
    robot = Robot(misty_ip)
    # Sound effect + voice line play in the background (paths are relative to this
    # directory; skipped when use_local_audio is false in MistyPilot_config.json)
    play_emotion_sounds(robot, "scare_background_music.mp3", "scared.mp3")
    # Perform fear actions (emotion, LED, movements)
    perform_fear(misty_ip, api_key)
    
    # Note: Audio plays in background, callback returns immediately
    
    
def cb_fear(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    WHEN TO USE:
    - User wants Misty to express fear, anxiety, or being scared

    Chinese keywords: 恐惧, 害怕, 恐怖, 惊恐, 恐慌
    English keywords: fear, scared, frightened, afraid, anxiety, terrified
    """
    fear(misty_ip, api_key)
    
