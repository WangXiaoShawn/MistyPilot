

import sys
import os
# Ensure current directory is in sys.path so we can import sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from local_audio import play_emotion_sounds
from typing import Optional
from typing import Dict, Any

def happy(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute happy emotion with sound effects.
    Plays local MP3 in parallel with happy actions.
    """
    robot = Robot(misty_ip)
    # Sound effect + voice line play in the background (paths are relative to this
    # directory; skipped when use_local_audio is false in MistyPilot_config.json)
    play_emotion_sounds(robot, "happy-huming.mp3", "happy_pure.mp3")
    # Perform happy actions (emotion, LED, movements)
    perform_happy(misty_ip, api_key)
    
    # Note: Audio plays in background, callback returns immediately
    
    
def cb_happy(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    WHEN TO USE:
    - User wants Misty to express happiness or joy
    Chinese keywords: 开心, 高兴, 快乐, 愉快, 喜悦
    English keywords: happy, joy, happiness, cheerful, pleased
    """
    happy(misty_ip, api_key)
    
if __name__ == "__main__":
    happy(misty_ip="<Misty robot IP>",api_key=None)