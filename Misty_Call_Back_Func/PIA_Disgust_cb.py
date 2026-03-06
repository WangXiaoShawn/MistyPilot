import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from typing import Optional
from typing import Dict, Any
import threading


    
def disgust(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute disgust emotion with sound effects.
    Plays local MP3 in parallel with disgust actions.
    """
    # Create robot instance for MP3 playback
    robot = Robot(misty_ip)
    
    # Play MP3 sound effect in a separate thread
    def _play_disgust_sound():
        # Warm-up: wake up audio hardware before playing actual sound
        import subprocess
        subprocess.run(['afplay', '-t', '0.05', '/System/Library/Sounds/Tink.aiff'], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/EffectSound/eww-sound.mp3")
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/MistySpeaking/disgusted.mp3")
    
    # Start MP3 playback in parallel (daemon thread - won't block in async context)
    sound_thread = threading.Thread(target=_play_disgust_sound, daemon=True)
    sound_thread.start()
    
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
    disgust(misty_ip="67.20.209.79",api_key=None)