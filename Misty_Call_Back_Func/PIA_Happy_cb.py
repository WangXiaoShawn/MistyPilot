

import sys
import os
# Ensure current directory is in sys.path so we can import sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from typing import Optional
from typing import Dict, Any
import threading

def happy(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute happy emotion with sound effects.
    Plays local MP3 in parallel with happy actions.
    """
    # Create robot instance for MP3 playback
    robot = Robot(misty_ip)
    
    # Play MP3 sound effect in a separate thread
    def _play_happy_sound():
        # Warm-up: wake up audio hardware before playing actual sound
        import subprocess
        subprocess.run(['afplay', '-t', '0.05', '/System/Library/Sounds/Tink.aiff'], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/EffectSound/happy-huming.mp3")
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/MistySpeaking/happy_pure.mp3")
    
    sound_thread = threading.Thread(target=_play_happy_sound, daemon=True)
    sound_thread.start()
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
    happy(misty_ip="67.20.209.79",api_key=None)