import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from typing import Optional
from typing import Dict, Any
import threading


    
def sad(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute sad emotion with sound effects.
    Plays local MP3 in parallel with sad actions.
    """
    # Create robot instance for MP3 playback
    robot = Robot(misty_ip)
    
    # Play MP3 sound effect in a separate thread
    def _play_sad_sound():
        # Warm-up: wake up audio hardware before playing actual sound
        import subprocess
        subprocess.run(['afplay', '-t', '0.05', '/System/Library/Sounds/Tink.aiff'], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/EffectSound/crying-said.mp3")
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/MistySpeaking/sad_lonely_heavy.mp3")
    
    # Start MP3 playback in parallel (daemon thread - won't block in async context)
    sound_thread = threading.Thread(target=_play_sad_sound, daemon=True)
    sound_thread.start()
    
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
    