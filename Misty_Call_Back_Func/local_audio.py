# -*- coding: utf-8 -*-
"""
Local sound-effect helper shared by the emotion callbacks.

- Resolves MP3 paths relative to this directory (no machine-specific absolute paths).
- Honors the ``use_local_audio`` switch in MistyPilot_config.json.
- Playback uses macOS ``afplay`` via Robot.play_local_mp3; on other platforms the
  callback still runs, only the sound is skipped.
"""
import json
import os
import subprocess
import threading
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_HERE, "..", "MistyPilot_config.json")
_WARMUP_SOUND = "/System/Library/Sounds/Tink.aiff"  # macOS only, used to wake the audio device


def sound_path(*parts: str) -> str:
    """Absolute path to a file under Misty_Call_Back_Func/ (e.g. sound_path("EffectSound", "x.mp3"))."""
    return os.path.join(_HERE, *parts)


def local_audio_enabled() -> bool:
    """Read ``use_local_audio`` from MistyPilot_config.json (defaults to True if missing/unreadable)."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return bool(json.load(f).get("use_local_audio", True))
    except Exception:
        return True


def play_emotion_sounds(robot, effect_file: str, speech_file: str) -> Optional[threading.Thread]:
    """
    Play EffectSound/<effect_file> then MistySpeaking/<speech_file> in a background
    daemon thread so the caller can start robot actions immediately.
    Returns the thread, or None when local audio is disabled.
    """
    if not local_audio_enabled():
        return None

    def _run():
        # Warm-up: wake up audio hardware before playing actual sound (best effort)
        try:
            subprocess.run(["afplay", "-t", "0.05", _WARMUP_SOUND],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except Exception:
            pass
        robot.play_local_mp3(sound_path("EffectSound", effect_file))
        robot.play_local_mp3(sound_path("MistySpeaking", speech_file))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
