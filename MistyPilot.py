# -*- coding: utf-8 -*-
"""
MistyPilot with Voice Control v3
Integrates faster-whisper transcription with MistyPilot task execution.
Press and hold 'c' to record, release to transcribe and execute.

Key improvement over v1/v2:
- selector_prompt is dynamically generated from cb_functions_summary.json
- No more hardcoded keyword lists in the router
- Adding a new PIA callback only requires writing a good docstring
"""

import sys
import termios
import tty
import time
import threading
import re
from concurrent.futures import ThreadPoolExecutor
import asyncio
import os
import json
import signal

import pyaudio
import numpy as np
from pynput import keyboard
from faster_whisper import WhisperModel

from voice_input_queue import get_voice_input_queue

# ==============================================================================
#  Configuration
# ==============================================================================

CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

HOLD_KEY = 'c'
WHISPER_MODEL_SIZE = "small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
BEAM_SIZE = 1
USE_VAD = False
FORCE_LANGUAGE = "zh" # zh or en
TASK = "transcribe"
MIN_RECORDING_DURATION = 1.0

is_recording = False
frames = []
lock = threading.Lock()
executor = None
misty_busy = False
last_busy_warning_time = 0
recording_start_time = 0
restart_requested = False

# ==============================================================================
#  Configuration Loading
# ==============================================================================

def load_config(config_filename="MistyPilot_config.json"):
    """Load MistyPilot configuration"""
    current_dir = os.path.dirname(__file__)
    config_path = os.path.join(current_dir, config_filename)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        return json.load(f)

# ==============================================================================
#  Terminal Control
# ==============================================================================

def set_terminal_noecho_cbreak():
    """Disable echo and set cbreak mode so keys won't print to screen"""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSADRAIN, new)
    return fd, old

def restore_terminal(fd, old):
    """Restore terminal settings"""
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except:
        pass

# ==============================================================================
#  Audio Processing
# ==============================================================================

def pcm16_bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert PCM16 bytes to float32 numpy array"""
    audio_i16 = np.frombuffer(pcm_bytes, dtype=np.int16)
    return audio_i16.astype(np.float32) / 32768.0

def transcribe_pcm_bytes(model: WhisperModel, pcm_bytes: bytes) -> str:
    """Transcribe audio bytes using faster-whisper"""
    audio = pcm16_bytes_to_float32(pcm_bytes)

    if audio.size < int(RATE * 0.15):
        return "(too short)"

    segments, _info = model.transcribe(
        audio,
        beam_size=BEAM_SIZE,
        vad_filter=USE_VAD,
        language=FORCE_LANGUAGE,
        task=TASK,
        condition_on_previous_text=False,
        temperature=0.0,
    )

    parts = []
    for seg in segments:
        t = (seg.text or "").strip()
        if t:
            parts.append(t)

    out = " ".join(parts).strip()
    return out if out else "(no speech detected)"

# ==============================================================================
#  Dynamic Selector Prompt Builder
# ==============================================================================

def _extract_tool_info(fname: str, docs: str) -> dict:
    """
    Parse structured fields from a callback docstring.
    Extracts: zh_keywords, en_keywords, constraints (DO NOT rules).
    """
    # Extract Chinese keywords line
    zh_match = re.search(r"Chinese keywords[:：](.*)", docs)
    zh_keywords = zh_match.group(1).strip() if zh_match else ""

    # Extract English keywords line
    en_match = re.search(r"English keywords[:：](.*)", docs)
    en_keywords = en_match.group(1).strip() if en_match else ""

    # Extract all DO NOT / WHEN NOT TO USE constraints
    constraints = re.findall(r"(?:DO NOT[^\n]+|WHEN NOT TO USE[^\n]*(?:\n- [^\n]+)*)", docs)
    constraints_clean = [c.strip() for c in constraints if c.strip()]

    # First meaningful line as summary (skip lines that are all caps headers like *** ... ***)
    summary = ""
    for line in docs.splitlines():
        line = line.strip()
        if line and not line.startswith("*") and not line.startswith("#"):
            summary = line
            break

    return {
        "fname": fname,
        "summary": summary,
        "zh_keywords": zh_keywords,
        "en_keywords": en_keywords,
        "constraints": constraints_clean,
    }


def build_selector_prompt(cb_summary_path: str) -> str:
    """
    Dynamically generate the SelectorGroupChat routing prompt by reading
    cb_functions_summary.json. No hardcoded keyword lists needed.

    Each PIA tool's docstring fields (keywords + constraints) are parsed and
    injected so the router LLM can make accurate decisions automatically.
    """
    cb_summary_path = os.path.abspath(cb_summary_path)
    if not os.path.exists(cb_summary_path):
        raise FileNotFoundError(f"cb_functions_summary.json not found: {cb_summary_path}")

    with open(cb_summary_path, "r", encoding="utf-8") as f:
        cb_summary = json.load(f)

    # Build the PIA tools section from parsed docstrings
    pia_tools_lines = []
    for fname, info in cb_summary.items():
        docs = info.get("docs", "")
        if not docs:
            continue
        tool = _extract_tool_info(fname, docs)

        entry = f"  [{fname}]\n"
        entry += f"    Summary   : {tool['summary']}\n"
        if tool["en_keywords"]:
            entry += f"    EN keywords: {tool['en_keywords']}\n"
        if tool["zh_keywords"]:
            entry += f"    ZH keywords: {tool['zh_keywords']}\n"
        for c in tool["constraints"]:
            entry += f"    CONSTRAINT : {c}\n"
        pia_tools_lines.append(entry)

    pia_tools_block = "\n".join(pia_tools_lines)

    prompt = f"""Select the next agent to speak.
{{roles}}
Conversation:
{{history}}
Participants: {{participants}}

========================
HARD OVERRIDE (absolute priority)
========================
If the user is indicating ANY of the following meta-intents, you MUST select MistySensorAgent_SOM:
a) Wants to switch from chatting to execution mode
   (e.g., "用技能", "技能模式", "let's use skills", "go to skill mode", "use the tool")

This rule overrides all other rules and any conversation context.

========================

PIA TOOL REGISTRY (MistySensorAgent_SOM capabilities)
========================
The following physical/sensor/media actions are available via MistySensorAgent_SOM.
If the user intent matches ANY of these tools, you MUST select MistySensorAgent_SOM.

{pia_tools_block}
Additionally, route to MistySensorAgent_SOM for:
- Any physical interaction: touch, bump, sensors, body parts, movement, camera, gestures
  (表演/跳舞/做动作/做手势/做表情/touch/tap/press/move/turn/photo/gesture)
- Any request to demonstrate or act out an emotion physically

========================
FALLBACK
========================
If the task is language-only (chat/story/Q&A/conversation) and does NOT match any
PIA tool or physical action above => MistyEmotionSpeakingAgent_SOM

Return ONLY one name from {{participants}}.
"""
return prompt


# ==============================================================================
#  MistyPilot Task Execution
# ==============================================================================

async def execute_misty_task(task: str):
    """
    Execute a task using MistyPilot system.
    selector_prompt is dynamically generated from cb_functions_summary.json.
    """
    global misty_busy

    try:
        misty_busy = True

        print(f"\n{'='*60}")
        print(f"[MistyPilot] Executing Task")
        print(f"{'='*60}")
        print(f"Task: {task}\n")

        from autogen_agentchat.teams import SelectorGroupChat
        from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
        from autogen_agentchat.ui import Console
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        from autogen_core.models import ModelFamily

        from PIA.MIsty_Process_State_Rehydrate import rehydrate_from_registry
        from Misty_callback_summary import process_all_cb_files
        from PIA.MistySensorAgent import create_misty_sensor_agent
        from SIA.MistyEmotionSpeakingAgent import create_misty_emotion_speaking_agent

        # 1. Clean temporary files
        for fname in ["misty_speaking_action_state.json", "thinking_model_power.json"]:
            if os.path.exists(fname):
                os.remove(fname)

        # 2. Restore state and regenerate callback summary
        rehydrate_from_registry("misty_proc_registry.json", mode="replace")
        process_all_cb_files()  # regenerates cb_functions_summary.json from latest docstrings

        # 3. Create fresh agent instances
        print("[Init] Creating fresh agent instances...")
        MistySensorAgent_SOM = create_misty_sensor_agent()
        MistyEmotionSpeakingAgent_SOM = create_misty_emotion_speaking_agent()
        print("[Init] Agents created successfully")

        # 4. Load configuration
        cfg = load_config()
        OPENAI_API_KEY = cfg.get("openai_api_key")
        model_name = cfg.get("llm_model", "gpt-4o-mini")

        # 5. Configure model
        if "gpt-5" in model_name.lower():
            model_family = ModelFamily.GPT_5
        elif "gpt-4" in model_name.lower():
            model_family = ModelFamily.GPT_4O
        else:
            model_family = ModelFamily.UNKNOWN

        model_client = OpenAIChatCompletionClient(
            model=model_name,
            api_key=OPENAI_API_KEY,
            model_info={
                "vision": False,
                "function_calling": False,
                "json_output": False,
                "family": model_family,
                "structured_output": False,
            }
        )

        # 6. Build selector prompt dynamically from cb_functions_summary.json
        cb_summary_path = cfg.get("CB_SUMMARY_JSON_dir", "./cb_functions_summary.json")
        selector_prompt = build_selector_prompt(cb_summary_path)
        print(f"[Router] selector_prompt built from {len(json.load(open(cb_summary_path)))} PIA tools")

        # 7. Create team
        team = SelectorGroupChat(
            participants=[MistySensorAgent_SOM, MistyEmotionSpeakingAgent_SOM],
            model_client=model_client,
            termination_condition=TextMentionTermination("TERMINATE") | MaxMessageTermination(20),
            selector_prompt=selector_prompt,
            allow_repeated_speaker=False,
        )

        # 8. Execute task
        await Console(team.run_stream(task=task))

        print(f"\n{'='*60}")
        print(f"[MistyPilot] Task Completed")
        print(f"{'='*60}\n")
        print("[Ready] Press and hold 'c' to record new command\n")

    except Exception as e:
        print(f"\n[Error] Task execution failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        misty_busy = False

        voice_queue = get_voice_input_queue()
        voice_queue.clear()
        print("[Cleanup] Voice queue cleared")
        print("[Cleanup] Task cleanup complete (fresh agents will be created for next task)")


def execute_task_in_background(task: str):
    """
    Execute MistyPilot task in a new event loop (background thread).
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(execute_misty_task(task))

    except Exception as e:
        print(f"[Error] Background execution failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if loop is not None:
            try:
                pending = asyncio.all_tasks(loop)
                for task_obj in pending:
                    task_obj.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
                print("[Cleanup] Event loop closed")
            except Exception as cleanup_error:
                print(f"[Cleanup] Warning: {cleanup_error}")

# ==============================================================================
#  Main Voice Control Loop
# ==============================================================================

def run_voice_control():
    """Main function to run voice-controlled MistyPilot v3"""
    global is_recording, frames, executor, misty_busy

    print("\n" + "=" * 60)
    print("MistyPilot with Voice Control v3")
    print("Dynamic PIA tool routing from cb_functions_summary.json")
    print("=" * 60)
    print()

    # Audio warm-up to prevent first syllable being clipped
    try:
        import subprocess
        print("Warming up audio system...", flush=True)
        subprocess.run(
            ['afplay', '-t', '0.2', '/System/Library/Sounds/Tink.aiff'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[Warn] Audio warm-up failed: {e}", flush=True)

    print("Loading faster-whisper model...", flush=True)
    model = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("Model ready.\n", flush=True)

    executor = ThreadPoolExecutor(max_workers=2)

    fd = None
    old_term = None
    try:
        fd, old_term = set_terminal_noecho_cbreak()
    except:
        pass

    audio = None
    stream = None

    try:
        print("Voice Control Active", flush=True)
        print("=" * 60, flush=True)
        print(f"Hold '{HOLD_KEY.upper()}' to record your command", flush=True)
        print("Release to transcribe and execute", flush=True)
        print(f"Press 'B' for quick APPROVE (when system asks for input)", flush=True)
        print(f"Press 'S' to stop music", flush=True)
        print(f"Press 'A' to restart the system", flush=True)
        print("Press Ctrl+C to quit.\n", flush=True)

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        print("Ready. Waiting for voice commands...\n", flush=True)

        def is_hold_key(k):
            try:
                if hasattr(k, "char") and k.char:
                    return k.char.lower() == HOLD_KEY.lower()
            except:
                return False
            return False

        def is_approve_key(k):
            try:
                if hasattr(k, "char") and k.char:
                    return k.char.lower() == 'b'
            except:
                return False
            return False

        def is_toggle_key(k):
            try:
                if hasattr(k, "char") and k.char:
                    return k.char.lower() == 'a'
            except:
                return False
            return False

        def is_stop_music_key(k):
            try:
                if hasattr(k, "char") and k.char:
                    return k.char.lower() == 's'
            except:
                return False
            return False

        def on_press(key):
            """Handle key press event"""
            global is_recording, frames, misty_busy, last_busy_warning_time, recording_start_time, restart_requested

            if is_stop_music_key(key):
                import subprocess as _sp
                r1 = _sp.run(["pkill", "-f", "afplay"], capture_output=True)
                r2 = _sp.run(["pkill", "-f", "ffplay"], capture_output=True)
                if r1.returncode == 0 or r2.returncode == 0:
                    print("\n[Audio] All audio stopped.\n", flush=True)
                else:
                    print("\n[Audio] No audio playing.\n", flush=True)
                return

            if is_toggle_key(key):
                import subprocess as _sp
                _sp.run(["pkill", "-f", "afplay"], capture_output=True)
                _sp.run(["pkill", "-f", "ffplay"], capture_output=True)
                print("\n[Audio] All audio stopped.", flush=True)
                print("[Restart] Restarting MistyPilot Voice Control...\n", flush=True)
                restart_requested = True
                with lock:
                    if is_recording:
                        is_recording = False
                        frames = []
                os.kill(os.getpid(), signal.SIGINT)
                return

            if is_approve_key(key):
                voice_queue = get_voice_input_queue()
                if voice_queue.is_waiting():
                    print("Quick Approve (B key) -> Sending 'APPROVE'\n", flush=True)
                    voice_queue.put("APPROVE")
                else:
                    print("[Info] System not waiting for input, 'B' key ignored.\n", flush=True)
                return

            if not is_hold_key(key):
                return

            voice_queue = get_voice_input_queue()

            if misty_busy and not voice_queue.is_waiting():
                current_time = time.time()
                if current_time - last_busy_warning_time > 2.0:
                    print("[Busy] MistyPilot is currently executing a task, please wait...\n", flush=True)
                    last_busy_warning_time = current_time
                return

            with lock:
                if is_recording:
                    return
                is_recording = True
                frames = []
                recording_start_time = time.time()

            if voice_queue.is_waiting():
                print("Recording your response...", flush=True)
            else:
                print("Recording your command...", flush=True)

        def on_release(key):
            """Handle key release event"""
            global is_recording, frames, recording_start_time

            if not is_hold_key(key):
                return

            with lock:
                if not is_recording:
                    return
                is_recording = False
                local_frames = frames
                frames = []
                recording_duration = time.time() - recording_start_time

            if recording_duration < MIN_RECORDING_DURATION:
                print(f"[Filtered] Recording too short ({recording_duration:.1f}s < {MIN_RECORDING_DURATION}s), ignoring.\n", flush=True)
                return

            if len(local_frames) < 2:
                print("[Warning] Recording too short, please try again.\n", flush=True)
                return

            pcm_bytes = b"".join(local_frames)
            start_t = time.time()
            print(f"Transcribing ({recording_duration:.1f}s recording)...", flush=True)

            def do_asr_and_execute():
                """Transcribe audio and execute task or send as interactive input"""
                global misty_busy

                voice_queue = get_voice_input_queue()

                text = transcribe_pcm_bytes(model, pcm_bytes)
                dt = time.time() - start_t
                print(f"Transcribed: \"{text}\" (ASR {dt:.2f}s)\n", flush=True)

                if text in ["(too short)", "(no speech detected)"]:
                    print("[Info] No valid speech detected, please try again.\n", flush=True)
                    return

                if voice_queue.is_waiting():
                    print("[Interactive] Sending voice input to MistyPilot...\n", flush=True)
                    voice_queue.put(text)
                else:
                    print("[MistyPilot] Starting task execution...\n", flush=True)
                    execute_task_in_background(text)

            executor.submit(do_asr_and_execute)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()

        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            with lock:
                if is_recording:
                    frames.append(data)

    except KeyboardInterrupt:
        if restart_requested:
            print("\n[Restart] Cleaning up before restart...", flush=True)
        else:
            print("\n[Exit] Shutting down...", flush=True)
    finally:
        import subprocess as _sp
        _sp.run(["pkill", "-f", "afplay"], capture_output=True)
        _sp.run(["pkill", "-f", "ffplay"], capture_output=True)
        print("[Cleanup] All audio processes terminated.", flush=True)

        try:
            if executor:
                executor.shutdown(wait=False, cancel_futures=True)
        except:
            pass

        try:
            if stream:
                stream.stop_stream()
                stream.close()
            if audio:
                audio.terminate()
        except:
            pass

        if fd is not None and old_term is not None:
            restore_terminal(fd, old_term)

        if restart_requested:
            print("[Restart] Relaunching...\n", flush=True)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            print("\n[Exit] MistyPilot Voice Control v3 stopped")

# ==============================================================================
#  Entry Point
# ==============================================================================

if __name__ == "__main__":
    run_voice_control()
