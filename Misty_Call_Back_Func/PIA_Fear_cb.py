import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from PIA_Actions import perform_wave_once_right,perform_happy,perform_sad,perform_fear,perform_surprise,perform_disgust,perform_rage
from CUBS_Misty_Only_Raw_Actions import Robot
from typing import Optional
from typing import Dict, Any
import threading


def fear(misty_ip: str, api_key: Optional[str] = None) -> None:
    """
    Execute fear emotion with sound effects.
    Plays local MP3 in parallel with fear actions.
    """
    # Create robot instance for MP3 playback
    robot = Robot(misty_ip)
    
    # Play MP3 sound effect in a separate thread
    def _play_fear_sound():
        # Warm-up: wake up audio hardware before playing actual sound
        import subprocess
        subprocess.run(['afplay', '-t', '0.05', '/System/Library/Sounds/Tink.aiff'], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[DEBUG] Playing fear sound...")
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/EffectSound/scare_background_music.mp3")
        robot.play_local_mp3("/Users/xiaowang/Documents/Code/MistyPilot/Misty_Call_Back_Func/MistySpeaking/scared.mp3")
    
    # Start MP3 playback in parallel (daemon thread - won't block in async context)
    sound_thread = threading.Thread(target=_play_fear_sound, daemon=True)
    sound_thread.start()
    
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
    
