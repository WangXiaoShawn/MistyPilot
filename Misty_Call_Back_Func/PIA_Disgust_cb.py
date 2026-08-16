import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from local_audio import play_emotion_sounds
from typing import Optional
from typing import Dict, Any


    
def disgust(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute disgust emotion with sound effects.
    Plays local MP3 in parallel with disgust actions.
    """
    robot = Robot(misty_ip)
    # Sound effect + voice line play in the background (paths are relative to this
    # directory; skipped when use_local_audio is false in MistyPilot_config.json)
    play_emotion_sounds(robot, "eww-sound.mp3", "disgusted.mp3")
    # Perform disgust actions (emotion, LED, movements)
    perform_disgust(misty_ip, api_key)
    
    # Note: Audio plays in background, callback returns immediately
      
def cb_disgust(evt: Dict[str, Any],misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    WHEN TO USE:
    - User wants **Misty to express** disgust, dislike, or feeling sick
    Chinese keywords: 恶心, 厌恶, 反感, 嫌弃, 讨厌
    English keywords: disgust, disgusting, dislike, gross, yuck, feeling sick
    """
    disgust(misty_ip, api_key)
    

if __name__ == "__main__":
    disgust(misty_ip="<Misty robot IP>",api_key=None)