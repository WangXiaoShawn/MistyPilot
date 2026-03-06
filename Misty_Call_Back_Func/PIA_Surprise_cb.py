import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from typing import Optional
from typing import Dict, Any
import threading


    
def surprise(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute surprise emotion with sound effects.
    Plays local MP3 in parallel with surprise actions.
    """
    # Create robot instance for MP3 playback
    robot = Robot(misty_ip)
    
    # Play MP3 sound effect in a separate thread
    def _play_surprise_sound():
        # Warm-up: wake up audio hardware before playing actual sound
        import subprocess
        subprocess.run(['afplay', '-t', '0.05', '/System/Library/Sounds/Tink.aiff'], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/EffectSound/surprise.mp3")
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/MistySpeaking/excited_surprise_strong.mp3")
    
    # Start MP3 playback in parallel (daemon thread - won't block in async context)
    sound_thread = threading.Thread(target=_play_surprise_sound, daemon=True)
    sound_thread.start()
    
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
    
