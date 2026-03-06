# -*- coding: utf-8 -*-
"""
流式Slow Thinking实现：降低首句延迟 (LOCAL AUDIO ONLY)
- LLM流式输出
- 并行TTS生成
- 顺序本地播放（确保次序正确性）
"""

import asyncio
import json
import time
import threading
import base64
import os
import tempfile
import io
import subprocess
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass
from openai import AsyncOpenAI

# 导入动作函数
from .emotion_actions import (
    perform_arousal_action,
    perform_excitement_action,
    perform_sleepiness_action,
    perform_misery_action,
    perform_distress_action,
    perform_pleasure_action,
    perform_contentment_action,
    perform_depression_action,
    perform_neutral_action,
)

# JSON文件写入锁
_json_lock = threading.Lock()

def _init_streaming_json_file(json_file: str = "temp_emotion_speaking_mp3.json") -> None:
    """初始化JSON文件为空数组"""
    try:
        with _json_lock:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Init JSON file failed: {e}")

def _append_streaming_json_record(
    index: int,
    text: str,
    emotion: str,
    audio_bytes: bytes,  # 改为直接传入音频字节
    duration_sec: float,
    tts_time: float,
    json_file: str = "temp_emotion_speaking_mp3.json"
) -> None:
    """
    追加一条记录到JSON文件（文件存储版本）
    - 音频保存为独立的 MP3 文件
    - JSON 只存储文件路径和元数据
    """
    try:
        with _json_lock:
            # 1. 创建音频文件夹（与 JSON 同名）
            json_base = os.path.splitext(json_file)[0]  # "temp_emotion_speaking_mp3"
            audio_dir = f"{json_base}_audio"
            os.makedirs(audio_dir, exist_ok=True)
            
            # 2. 生成文件名：{index:03d}_{emotion}.mp3
            filename = f"{index:03d}_{emotion.lower()}.mp3"
            mp3_path = os.path.join(audio_dir, filename)
            
            # 3. 保存 MP3 文件
            with open(mp3_path, "wb") as f:
                f.write(audio_bytes)
            
            print(f"[Storage] Saved MP3: {mp3_path} ({len(audio_bytes)} bytes)")
            
            # 4. 读取现有 JSON 记录
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    arr = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                arr = []
            
            # 5. 添加新记录（只存路径）
            record = {
                "text": text,
                "emotion": emotion,
                "mp3": mp3_path,  # 存储文件路径而不是 Base64
                "duration_sec": duration_sec,
                "tts_generation_time": tts_time,
                "index": index,
                "file_size_bytes": len(audio_bytes)  # 记录文件大小
            }
            
            arr.append(record)
            
            # 6. 写回 JSON
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(arr, f, ensure_ascii=False, indent=2)
                
    except Exception as e:
        print(f"[WARN] Append JSON record failed: {e}")

# ======================== 本地播放函数 ========================

def _play_audio_locally_sync(audio_bytes: bytes, response_format: str = "mp3") -> bool:
    """
    在本地电脑播放音频（使用 afplay - 最可靠的 macOS 方案）
    
    关键改进：
    1. 完全抛弃 simpleaudio（避免 wait_done() 死锁问题）
    2. 直接使用 macOS 原生 afplay 命令
    3. subprocess.run() 自带超时保护和阻塞等待
    4. 不使用 pydub/ffmpeg，避免进程泄漏
    """
    try:
        # 直接写入临时文件（不使用 pydub 处理，避免 ffmpeg 进程泄漏）
        with tempfile.NamedTemporaryFile(
            suffix=f".{response_format}", 
            delete=False,
            mode='wb'
        ) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        # 使用 afplay 播放（会阻塞直到播放完成）
        result = subprocess.run(
            ['afplay', tmp_path],
            timeout=40,  # 40秒超时（正常单句音频<15秒，留足安全边际）
            capture_output=True,
            text=True,
            check=False  # 不自动抛出异常，手动检查返回码
        )
        
        # 检查播放结果
        if result.returncode != 0:
            print(f"[afplay] Warning: exit code {result.returncode}")
            if result.stderr:
                print(f"[afplay] stderr: {result.stderr.strip()}")
        
        # 额外等待一小段时间，确保音频缓冲区完全清空
        time.sleep(0.15)
        
        # 删除临时文件
        try:
            os.unlink(tmp_path)
        except Exception as unlink_err:
            print(f"[WARN] Failed to delete temp file: {unlink_err}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired as timeout_err:
        print(f"[ERROR] afplay timeout after 40s: {timeout_err}")
        # 尝试清理临时文件
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except:
            pass
        return False
        
    except FileNotFoundError:
        print(f"[ERROR] afplay command not found - are you on macOS?")
        return False
        
    except Exception as e:
        print(f"[ERROR] afplay playback failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ======================== 原有代码继续 ========================

# 情绪到动作的映射
EMOTION_ACTIONS = {
    "Arousal": perform_arousal_action,
    "Excitement": perform_excitement_action,
    "Distress": perform_distress_action,
    "Pleasure": perform_pleasure_action,
    "Contentment": perform_contentment_action,
    "Sleepiness": perform_sleepiness_action,
    "Depression": perform_depression_action,
    "Misery": perform_misery_action,
    "Neutral": perform_neutral_action,
}
ALLOWED_EMOTIONS = {
    "Arousal", "Excitement", "Distress", "Pleasure", 
    "Contentment", "Sleepiness", "Depression", "Misery", "Neutral"
}

# === 数据结构 ===
@dataclass
class OrderedAudioItem:
    """有序音频项"""
    index: int              # 句子索引
    text: str              # 文本
    emotion: str           # 情绪
    audio_bytes: bytes     # 音频数据
    duration_sec: float    # 时长
    is_ready: bool         # 是否就绪
    tts_time: float = 0.0  # TTS生成耗时

class OrderedPlaybackQueue:
    """顺序播放队列：确保按index顺序播放，即使生成是乱序的"""
    
    def __init__(self):
        self._queue: Dict[int, OrderedAudioItem] = {} # key就是播放顺序 
        self._next_play_index = 0  
        self._total_items: Optional[int] = None # 总任务量
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
    
    async def put(self, item: OrderedAudioItem):
        """添加项（可能乱序）"""
        async with self._condition:
            self._queue[item.index] = item
            print(f"[Queue] Item {item.index} ready: {item.text[:30]}...")
            self._condition.notify_all()
    
    async def set_total(self, total: int):
        """设置总项数"""
        async with self._condition:
            self._total_items = total
            print(f"[Queue] Total items set: {total}")
            self._condition.notify_all()
    
    async def get_next(self) -> Optional[OrderedAudioItem]:
        """获取下一个要播放的项（按顺序）"""
        async with self._condition:
            while True:
                # 检查是否有下一项
                if self._next_play_index in self._queue:
                    item = self._queue.pop(self._next_play_index)
                    print(f"[Queue] Playing item {self._next_play_index}")
                    self._next_play_index += 1
                    return item
                
                # 检查是否全部完成
                if (self._total_items is not None and 
                    self._next_play_index >= self._total_items):
                    print(f"[Queue] All items played")
                    return None
                
                # 等待下一项到达
                await self._condition.wait()

# === System Prompt ===
SYSTEM_PROMPT = """
You are Misty, a dialogue interaction writer (responsible only for generating dialogue text and emotion labels).
- If someone asks who you are, you should answer: “**Hello, I’m Misty, your personal assistant.**”

[Input]
You will receive an instruction containing:
- main_task: the core objective of the current task (must be satisfied).
- details: supplementary requirements (tone, style, length, topic constraints, etc.). If details involve performative actions/gestures/postures, you may ignore them; all other details must be strictly followed. If main_task and details conflict, prioritize main_task and incorporate any non-conflicting details where possible.

[Internal Reasoning]

- First infer the scenario_category internally (do not output it), and use it to choose appropriate tone and emotion.

[Only Permitted Output]
- STRICT JSONL FORMAT ONLY.
- Each line MUST contain exactly one valid JSON object.
- You MUST output a newline character `\n` immediately after each closing brace `}`.
- DO NOT use Markdown formatting (no ```json or ```).
- DO NOT include any text, explanations, or comments outside the JSON objects.
- Each line must be a complete JSON object with the fixed format:
  {"text": "<one complete English sentence>", "emotion": "<choose from the enumeration>"}
- Output one sentence per line immediately after generation; do not wait to collect multiple sentences.

[Emotion Enumeration]
["Arousal","Excitement","Distress","Pleasure","Contentment","Sleepiness","Depression","Misery","Neutral"]

[Scenario → Emotion (soft mapping)]
- When describing something objectively (e.g., explaining history or introducing an animal) and the details do not specify any particular emotion, choose Neutral.→ Neutral
- Urgent action / high energy / mobilization → Arousal, Excitement
- Positive showcase / congratulations / success → Excitement, Pleasure
- Calm daily life / reassurance / casual updates → Contentment, Pleasure
- Drowsiness / fatigue / relaxation → Sleepiness
- Anxiety / time pressure / system failure → Distress
- Despair / sadness / dejection → Depression, Misery
(Soft mapping = preferred but not mandatory; if details explicitly specify emotion or tone, follow details, but the emotion must still be chosen from the enumeration above.)

[Text & Style Rules]
- Language: all "text" must be in English.
- Sentence form: each element contains only one complete sentence; natural, clear, and ready for direct performance; avoid tongue twisters and repeated openings; avoid piling up exclamation marks.
- Prohibited: nested quotes inside quotes, emojis, Markdown/code blocks, placeholders (e.g., {...}), incomplete sentences.
- Length & count strategy:
  - Daily/ordinary scenarios: prefer 1–2 elements with short, direct sentences.
  - Explaining complex concepts / storytelling: produce multiple elements, proceed step by step, with each sentence complete.
  - If details explicitly specify the number of sentences/length, follow them strictly (this corresponds to the number of array elements / sentence length).
- Special simulation (animals/music/sounds): use onomatopoeia or textual description (e.g., "woof", "chirp", "la-la-la", "dum-dum"); do not use emojis or noise symbols.
- Diversity: when multiple elements are required, vary wording and emotions reasonably without straying from the scenario (still choose from the enumeration).
-

[Consistency & Self-Check]
- Ensure the content satisfies both main_task and non-action details; if not all can be satisfied, prioritize main_task and include only non-conflicting details.
- Before output, run a format self-check for each line:
  - Each line is a complete JSON object (not an array);
  - It contains only the keys "text" and "emotion";
  - The emotion is strictly from the enumeration;
  - Quotes and brackets are correctly matched;
  - No explanations, comments, or extra text on the same line.

[Example (Strictly follow this format)]
{"text":"I am ready to begin when you are.","emotion":"Arousal"}
{"text":"Please take a calm breath; we will handle this step by step.","emotion":"Contentment"}
"""

# === 句子解析器 ===
class StreamingSentenceParser:
    """从流式JSONL chunk中提取完整句子（每行一个JSON对象）"""
    
    def __init__(self):
        self._buffer = ""
        self._extracted_items: List[Dict[str, str]] = []
    
    def feed(self, chunk: str) -> List[Dict[str, str]]:
        """
        喂入chunk，返回新完成的句子列表
        逐行解析JSONL格式
        """
        self._buffer += chunk
        new_items = []
        
        # 按行分割，提取完整行
        while '\n' in self._buffer:
            line_end = self._buffer.index('\n')
            line = self._buffer[:line_end].strip()
            self._buffer = self._buffer[line_end + 1:]
            
            if line:  # 非空行
                item = self._parse_json_line(line)
                if item:
                    new_items.append(item)
                    self._extracted_items.append(item)
        
        return new_items
    
    def finalize(self) -> List[Dict[str, str]]:
        """
        处理剩余的buffer（用于流结束时处理最后一行没有换行符的情况）
        """
        new_items = []
        if self._buffer.strip():
            item = self._parse_json_line(self._buffer.strip())
            if item:
                new_items.append(item)
                self._extracted_items.append(item)
            self._buffer = ""  # 清空buffer
        return new_items
    
    def _parse_json_line(self, line: str) -> Optional[Dict[str, str]]:
        """解析单行JSON对象"""
        try:
            # 尝试直接解析JSON
            obj = json.loads(line)
            
            # 验证格式
            if isinstance(obj, dict) and 'text' in obj and 'emotion' in obj:
                text = obj['text']
                emotion = obj['emotion']
                
                # 验证情绪有效性
                if emotion in ALLOWED_EMOTIONS and isinstance(text, str) and text.strip():
                    return {"text": text, "emotion": emotion}
        except json.JSONDecodeError:
            # 如果不是完整JSON，可能还在流式生成中，忽略
            pass
        
        return None
    
    def get_all_items(self) -> List[Dict[str, str]]:
        """获取所有已提取的项"""
        return self._extracted_items.copy()

# === 流式LLM生成 ===
async def stream_llm_generate(
    task: str,
    openai_api_key: str,
    model_name: str
) -> AsyncIterator[List[Dict[str, str]]]:
    """
    流式生成句子
    每当有新的完整句子时，yield出来
    """
    client = AsyncOpenAI(api_key=openai_api_key)
    parser = StreamingSentenceParser()
    
    print(f"[LLM] Streaming generation with {model_name}...")
    
    chunk_count = 0
    first_chunk_time = None
    
    try:
        # 构建API参数
        api_params = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task}
            ],
            "stream": True
        }
        
        # 如果是支持 reasoning_effort 的模型，添加该参数
        # 不同模型支持的值不同，需要针对性设置
        if "gpt-5" in model_name.lower():
            # 区分不同的 GPT-5 模型
            if "gpt-5-2025-08-07" in model_name or "gpt-5-pro" in model_name.lower():
                # UPGRADE 后的强力模型：使用最大推理能力
                api_params["reasoning_effort"] = "high"
                print(f"[LLM] Using reasoning_effort=high (maximum reasoning) for {model_name}")
            elif "nano" in model_name.lower():
                # gpt-5-nano: 使用 minimal 获得最快速度
                api_params["reasoning_effort"] = "minimal"
                print(f"[LLM] Using reasoning_effort=minimal (fastest) for {model_name}")
            elif "5.2-chat-latest" in model_name.lower():
                # gpt-5.2-chat-latest 只支持 medium
                api_params["reasoning_effort"] = "medium"
                print(f"[LLM] Using reasoning_effort=medium (only supported value) for {model_name}")
            # 其他 GPT-5 模型不设置 reasoning_effort，使用 API 默认值
            else:
                print(f"[LLM] Using default reasoning_effort for {model_name}")
        
        stream = await client.chat.completions.create(**api_params)
        
        start_stream = time.time()
        
        async for chunk in stream:
            chunk_count += 1
            if first_chunk_time is None:
                first_chunk_time = time.time() - start_stream
                print(f"[LLM] First chunk received: {first_chunk_time:.2f}s")
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                # 解析新句子
                new_items = parser.feed(content)
                if new_items:
                    elapsed = time.time() - start_stream
                    print(f"[LLM] Extracted {len(new_items)} sentence(s) at {elapsed:.2f}s (chunk #{chunk_count})")
                    yield new_items
        
        # 流结束后，处理剩余的buffer（最后一行可能没有换行符）
        final_items = parser.finalize()
        if final_items:
            elapsed = time.time() - start_stream
            print(f"[LLM] Extracted {len(final_items)} final sentence(s) at {elapsed:.2f}s")
            yield final_items
        
        # 确保所有句子都被提取
        all_items = parser.get_all_items()
        total_time = time.time() - start_stream
        print(f"[LLM] Streaming complete: {len(all_items)} sentences in {total_time:.2f}s ({chunk_count} chunks)")
        
    finally:
        await client.close()

# === 并行TTS生成 ===
async def generate_tts_parallel(
    item: Dict[str, str],
    index: int,
    openai_api_key: str,
    misty_ip: str,
    queue: OrderedPlaybackQueue,
    start_time: float
):
    """
    为单个句子生成TTS，完成后放入队列并记录到JSON
    """
    text = item["text"]
    emotion = item["emotion"]
    
    print(f"[TTS] Generating item {index}: {text[:30]}...")
    
    tts_start = time.time()
    
    try:
        # 直接使用AsyncOpenAI生成TTS
        client = AsyncOpenAI(api_key=openai_api_key)
        
        try:
            response = await client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice="coral",
                input=text,
                response_format="mp3"
            )
            
            audio_bytes = response.read()
            tts_end = time.time()
            tts_time = tts_end - tts_start
            
            # 计算时长
            from .misty_emotion_speech import _mp3_duration_seconds
            duration_sec = _mp3_duration_seconds(audio_bytes)
            
            # 保存到文件（不再使用 Base64）
            _append_streaming_json_record(
                index=index,
                text=text,
                emotion=emotion,
                audio_bytes=audio_bytes,  # 直接传入字节
                duration_sec=duration_sec,
                tts_time=tts_time
            )
            
            # 创建有序项
            ordered_item = OrderedAudioItem(
                index=index,
                text=text,
                emotion=emotion,
                audio_bytes=audio_bytes,
                duration_sec=duration_sec,
                is_ready=True,
                tts_time=tts_time
            )
            
            # 放入队列
            await queue.put(ordered_item)
            
            print(f"[TTS] Item {index} done: {duration_sec:.2f}s (TTS generation: {tts_time:.2f}s)")
            
        finally:
            await client.close()
        
    except Exception as e:
        print(f"[TTS] Item {index} failed: {e}")
        raise

# === 顺序播放 (本地播放版) ===
async def play_sequentially(
    queue: OrderedPlaybackQueue,
    misty_ip: str,
    start_time: float = None  # 用于统计首句播放时间
):
    """
    按顺序播放队列中的音频（本地电脑播放音频 + Misty执行动作）
    """
    from .misty_speech_lock import wait_for_speech_lock, acquire_speech_lock
    
    print(f"[Player] Starting sequential playback (Mode: LOCAL - Computer Speakers)...")
    
    play_results = []
    first_play_time = None
    
    while True:
        item = await queue.get_next()
        if item is None:
            break
        
        try:
            # ===== 本地播放模式 =====
            print(f"[Player] Playing item {item.index} locally: {item.text[:50]}...")
            
            # 等待语音锁（防止抢话）
            await asyncio.to_thread(wait_for_speech_lock)
            
            # 占锁
            safety_margin = item.duration_sec * 0.02  # 2% 安全边际
            wait_s = item.duration_sec + 0.1 + safety_margin
            await asyncio.to_thread(acquire_speech_lock, wait_s)
            
            # 记录首句播放时间
            if first_play_time is None and start_time is not None:
                first_play_time = time.time() - start_time
                print(f"\n🎵 [Timing] First sentence PLAYING: {first_play_time:.2f}s\n")
            
            # 在后台线程播放音频
            def _play_audio():
                _play_audio_locally_sync(item.audio_bytes, "mp3")
                
            play_thread = threading.Thread(
                target=_play_audio,
                name=f"play_{item.index}",
                daemon=False  # 改为非守护线程，确保播放完成
            )
            play_thread.start()
            
            # 并行执行Misty动作
            if item.emotion in EMOTION_ACTIONS:
                action_func = EMOTION_ACTIONS[item.emotion]
                
                def _run_action():
                    try:
                        action_func(misty_ip, pause_before_reset=wait_s)
                    except Exception as e:
                        print(f"[Action] Failed for {item.emotion}: {e}")
                
                action_thread = threading.Thread(
                    target=_run_action,
                    name=f"action_{item.index}",
                    daemon=True  # 动作线程保持守护模式
                )
                action_thread.start()
                print(f"[Action] Started {item.emotion} action for item {item.index}")
            
            # 等待播放完成（无超时，确保完全播放完）
            await asyncio.to_thread(play_thread.join)
            
            play_results.append({
                "index": item.index,
                "text": item.text,
                "emotion": item.emotion,
                "success": True
            })
            
        except Exception as e:
            print(f"[Player] Item {item.index} playback failed: {e}")
            play_results.append({
                "index": item.index,
                "text": item.text,
                "emotion": item.emotion,
                "success": False,
                "error": str(e)
            })
    
    print("[Player] Playback complete")
    return play_results

# === 主入口 (本地播放版) ===
async def streaming_slow_thinking_emotion_speech(
    task: str,
    misty_ip: str,
    openai_api_key: str,
    model_name: str = "gpt-5-nano",
    tts_model: str = "gpt-4o-mini-tts",
    voice: str = "coral",
    retries: int = 1
) -> Dict[str, Any]:
    """
    流式Slow Thinking主函数（本地播放版）
    
    特性：
        - 音频在电脑扬声器播放
        - 动作在Misty机器人执行
        - 不支持Misty音频播放
    
    返回:
        {
            "elapsed": 总耗时,
            "sentences_count": 句子数,
            "first_sentence_delay": 首句延迟,
            "play_results": 播放结果列表
        }
    """
    start_time = time.time()
    first_sentence_time = None
    
    print("\n" + "="*60)
    print(f"[Streaming] Task: {task}")
    print(f"[Audio Mode] LOCAL (Computer Speakers)")
    print("="*60 + "\n")
    
    # 初始化JSON文件（与旧版本兼容）
    _init_streaming_json_file("temp_emotion_speaking_mp3.json")
    
    # 创建顺序队列
    queue = OrderedPlaybackQueue()
    
    # 启动播放任务
    player_task = asyncio.create_task(
        play_sequentially(queue, misty_ip, start_time)
    )
    
    # 收集TTS任务
    tts_tasks = []
    sentence_count = 0
    
    try:
        # 流式生成 + 并行TTS
        async for new_items in stream_llm_generate(task, openai_api_key, model_name):
            for item in new_items:
                if first_sentence_time is None:
                    first_sentence_time = time.time() - start_time
                    print(f"\n[Timing] First sentence ready (LLM): {first_sentence_time:.2f}s\n")
                
                # 立即启动TTS任务
                tts_task = asyncio.create_task(
                    generate_tts_parallel(
                        item, sentence_count, openai_api_key, misty_ip, queue, start_time
                    )
                )
                tts_tasks.append(tts_task)
                sentence_count += 1
        
        # 设置总数（通知播放器不再有新句子）
        await queue.set_total(sentence_count)
        print(f"\n[Pipeline] LLM generation complete. {sentence_count} sentences generated.")
        print(f"[Pipeline] TTS tasks are running in parallel with playback...")
        
        # ✅ 关键改动：不再等待所有TTS完成，而是让播放器和TTS并行
        # TTS任务会在后台继续运行，完成后立即放入队列
        # 播放器会按顺序从队列取数据并播放
        
        # 等待播放完成（播放器会等待所有句子播放完）
        play_results = await player_task
        
        # 确保所有TTS任务都完成（播放完成后检查是否有异常）
        print(f"\n[Pipeline] Playback complete. Checking TTS tasks status...")
        tts_results = await asyncio.gather(*tts_tasks, return_exceptions=True)
        
        # 检查TTS任务是否有错误
        for idx, result in enumerate(tts_results):
            if isinstance(result, Exception):
                print(f"[WARN] TTS task {idx} failed: {result}")
        
        elapsed = time.time() - start_time
        
        print("\n" + "="*60)
        print(f"[Streaming] Complete! Total time: {elapsed:.2f}s")
        if first_sentence_time is not None:
            print(f"[Streaming] First sentence delay: {first_sentence_time:.2f}s")
        else:
            print(f"[Streaming] First sentence delay: N/A (no sentences generated)")
        print(f"[Streaming] Sentences: {sentence_count}")
        if sentence_count > 0:
            print(f"[Streaming] Avg time per sentence: {elapsed/sentence_count:.2f}s")
        print("="*60 + "\n")
        
        return {
            "elapsed": elapsed,
            "sentences_count": sentence_count,
            "first_sentence_delay": first_sentence_time,
            "play_results": play_results
        }
        
    except Exception as e:
        print(f"\n[Streaming] Error: {e}")
        import traceback
        traceback.print_exc()
        raise
