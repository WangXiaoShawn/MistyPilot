# -*- coding: utf-8 -*-                                                             ### file encoding
# 文件：misty_pipeline_entry.py

import asyncio
import json
import threading
import queue
from typing import Optional, Dict, Any
from typing_extensions import Annotated
from pathlib import Path
import os


# === 固定依赖（同步实现，统一丢到线程里跑） =========================================
from .misty_fast_thinking_emotion_speech import fast_thinking_emotion_speech          ### FAST 分支（同步）
from .streaming_slow_thinking_emotion_speech import streaming_slow_thinking_emotion_speech  ### SLOW 分支（流式，默认）
from .misty_speaking_action_memory import (                                           ### 向量库（同步）
    init_client, get_or_create_collection, upsert_texts, query_emotion_action_speak_task
)
from .task_memory_action_utils import (                                               ### 文件/状态（同步）
 archive_temp_mp3_json
)
from .sync_curr_task_set import clarify_and_update, load_state, reset_state
from .fast_slow_thinking_state import load_thinking_model_power, update_thinking_model_power


def load_config(config_filename="MistyPilot_config.json"):
    """
    加载上一层目录的配置文件
    :param config_filename: 配置文件名 (默认 config.json)
    :return: 配置字典 config
    """
    # 获取当前文件所在目录
    current_dir = os.path.dirname(__file__)
    
    # 拼接到上一层目录
    config_path = os.path.join(current_dir, "..", config_filename)
    config_path = os.path.abspath(config_path)  # 转绝对路径
    
    # 读取 JSON 配置
    with open(config_path, "r") as f:
        config = json.load(f)
    
    return config

# ======================== 工具：在线程中新建事件循环（给同步外壳用） =================
def _run_coro_in_new_loop_sync(coro) -> Any:
    """在新线程里创建独立事件循环执行协程，返回结果或抛出异常。"""
    q: "queue.Queue[tuple[bool, Any]]" = queue.Queue()

    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 1. 设置异常处理器来屏蔽 "Event loop is closed" 噪音
        def _suppress_loop_closed_handler(loop, context):
            msg = context.get("message", "")
            exc = context.get("exception")
            # 如果是 loop closed 错误，直接忽略
            if "Event loop is closed" in msg or (exc and "Event loop is closed" in str(exc)):
                return
            # 否则调用默认处理
            loop.default_exception_handler(context)
            
        loop.set_exception_handler(_suppress_loop_closed_handler)

        try:
            # 2. 手动运行 Loop
            res = loop.run_until_complete(coro)
            q.put((True, res))
        except Exception as e:
            q.put((False, e))
        finally:
            # 3. 极其激进的清理策略
            try:
                # 取消所有剩余任务
                tasks = asyncio.all_tasks(loop)
                for t in tasks: 
                    t.cancel()
                
                # 等待任务取消完成（屏蔽取消错误）
                if tasks:
                    loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                
                # 关闭异步生成器
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass # 清理阶段的任何错误都忽略
            finally:
                loop.close()

    t = threading.Thread(target=_runner, name="isolated_asyncio_runner", daemon=True)
    t.start()
    ok, val = q.get()
    if ok:
        return val
    raise val



# ... (imports remain)

# ======================== 全局缓存：配置与DB连接 =================
_CACHED_CONFIG = None
_CACHED_DB_COLLECTION = None
_INIT_LOCK = threading.Lock()

def get_cached_config():
    """获取或加载全局配置（线程安全）"""
    global _CACHED_CONFIG
    if _CACHED_CONFIG is None:
        with _INIT_LOCK:
            if _CACHED_CONFIG is None:
                _CACHED_CONFIG = load_config()
    return _CACHED_CONFIG

def get_cached_collection():
    """获取 or 初始化全局向量库集合（线程安全）"""
    global _CACHED_DB_COLLECTION
    if _CACHED_DB_COLLECTION is None:
        with _INIT_LOCK:
            if _CACHED_DB_COLLECTION is None:
                cfg = get_cached_config()
                store_dir = cfg.get("store_dir", "./misty_emotion_action_speaking_store")
                collection_name = cfg.get("collection", "text-embedding-3-large")
                
                print(f"[DEBUG] Initializing DB Connection: dir={store_dir}, col={collection_name}")
                client = init_client(store_dir)
                _CACHED_DB_COLLECTION = get_or_create_collection(client, name=collection_name)
    return _CACHED_DB_COLLECTION


async def fast_slow_thinking_emotion_speech_async(
    task: Annotated[
        str,
        ("the task executed by this function")
    ],
) -> str:
    ### 1) 配置与向量库（使用全局缓存优化性能）
    # 注意：首次调用仍可能较慢（初始化DB），后续调用将复用连接
    
    # 获取缓存配置
    cfg = get_cached_config()
    # print("[DEBUG] Using cached config")

    misty_ip = cfg["misty_ip"]
    openai_api_key = cfg["openai_api_key"]
    model_name = cfg.get("llm_model", "gpt-5-nano")
    retries = int(cfg.get("retries", 1))
    threshold = float(cfg.get("threshold", 0.2))
    base_model = cfg.get("llm_model", "gpt-5-nano")
    powerful_model = cfg.get("stronger_model_name", "gpt-5-2025-08-07")

    # 获取缓存集合 (首次可能涉及I/O，建议仍放 thread 中以免阻塞，但后续极快)
    # 为了简化逻辑，这里直接调用同步的 get_cached_collection()，
    # 假设 Chroma 客户端创建后的内存操作够快。若担心首次阻塞，可保留 to_thread
    col = await asyncio.to_thread(get_cached_collection)
    
    # print(f"[DEBUG] misty_ip={misty_ip}, model_name={model_name}, retries={retries}, threshold={threshold}")
    # print("[DEBUG] Collection ready (cached)")

    prev_state = await asyncio.to_thread(load_state)                                                          ### 读取上次任务状态（文件 I/O）
    print("[DEBUG] Previous state loaded:", prev_state)
    prev_task = (prev_state.get("task") or "").strip()                                                        ### 上次任务名
    prev_details = (prev_state.get("details") or "").strip()                                                  ### 上次任务细节

    ### 2) 模型能力升级/降级指令（不改变：均放线程池）
    normalized = task.strip().upper()                                                                         ### 规格化指令大小写
    is_upgrade =  "UPGRADE" in normalized                                                                     ### 升级标记
    is_downgrade = "DOWNGRADE" in normalized                                                                  ### 降级标记

    if is_upgrade:
        print("[DEBUG] Command = UPGRADE → switch to stronger model and re-run last task if exists")
        await asyncio.to_thread(update_thinking_model_power, powerful_model)                                  ### 升级主干模型（文件 I/O/状态写入）
        thinking_model_name = await asyncio.to_thread(load_thinking_model_power)                              ### 读取当前主干模型（文件 I/O）
        print(f"[DEBUG] thinking_model_name(after upgrade)={thinking_model_name}")

        if not prev_task:                                                                                     ### 无历史任务就只更新模型
            return f"[UPGRADE] Backbone model switched to '{thinking_model_name}', but no previous task to re-execute."
        slow_thinking_task = f"Main task: {prev_task} | Task details: {prev_details}"                         ### 拼接上次任务
        print("[DEBUG] slow_thinking_task (UPGRADE branch):", slow_thinking_task)
        await streaming_slow_thinking_emotion_speech(                                                         ### 用流式SLOW复跑上次任务
            task=slow_thinking_task,
            misty_ip=misty_ip,
            openai_api_key=openai_api_key,
            model_name=thinking_model_name,
            retries=retries
        )
        return f"[UPGRADE] Backbone model switched to '{thinking_model_name}'. Re-executed previous task with SLOW mode."

    if is_downgrade:
        print("[DEBUG] Command = DOWNGRADE → switch to base model only (no execution)")
        await asyncio.to_thread(update_thinking_model_power, base_model)                                      ### 降级至基础主干模型
        thinking_model_name = await asyncio.to_thread(load_thinking_model_power)                              ### 读取当前主干模型
        print(f"[DEBUG] thinking_model_name(after downgrade)={thinking_model_name}")
        return f"[DOWNGRADE] Backbone model switched to '{thinking_model_name}'. State updated only; no task executed."

    ### 3) MEMORY 分支（放线程池）
    if task == "MEMORY":
        print("[DEBUG] Entering MEMORY branch")
        if not prev_task:                                                                                     ### 无历史任务，不可归档
            print("[DEBUG] No previous task found to store")
            return "No storable file available; let Misty complete a task first."
        new_file_path = await asyncio.to_thread(archive_temp_mp3_json)                                        ### 归档产生路径（文件 I/O）
        print("[DEBUG] Archived file path:", new_file_path)
        if not new_file_path:                                                                                 ### 没有可归档文件
            return "No generated file found; re-execute the previous task before archiving."
        
        full_task_description = f"{prev_task}"
        await asyncio.to_thread(upsert_texts, col, texts=full_task_description, paths=new_file_path)         ### 向量库入库（I/O）
        print(f"[DEBUG] Upsert completed for MEMORY task with full description: {full_task_description}")
        return "MEMORY archive completed."

    ### 4) NEW 分支：仅此处尝试 FAST（一次机会），失败则 SLOW（全部放线程池）
    if "NEW" in task:
        print("[DEBUG] Entering NEW branch with raw task:", task)
        clean_task = task.replace("NEW_", "", 1).replace("NEW", "", 1).strip()                                ### 去 NEW 前缀
        print("[DEBUG] Cleaned task (NEW branch):", clean_task)

        await asyncio.to_thread(reset_state)                                                                   ### 清空当前状态（文件 I/O）
        await asyncio.to_thread(update_thinking_model_power, base_model)                                       ### 回到基础主干模型（文件 I/O）
        thinking_model_name = await asyncio.to_thread(load_thinking_model_power)                               ### 读取当前主干模型名
        print(f"[DEBUG] thinking_model_name(NEW)={thinking_model_name}")

        curr_state = await asyncio.to_thread(                                                                  ### 只澄清一次（里面若有 I/O/HTTP 也被隔离）
            clarify_and_update,
            clean_task,
            openai_api_key=openai_api_key,
            model=model_name
        )
        print("[DEBUG] Current state after clarify_and_update (NEW):", curr_state)

        main_task = (curr_state.get("task") or "").strip()                                                     ### 取澄清后的任务名
        curr_task_details = (curr_state.get("details") or "").strip()                                          ### 取澄清后的细节

        json_path = await asyncio.to_thread(                                                                   
            query_emotion_action_speak_task, col, main_task, threshold=threshold                               ### 仅 NEW 尝试 FAST：向量库匹配
        )
        print("[DEBUG] Query result (NEW branch):", json_path)

        if json_path is not None:                                                                              ### 命中 → FAST
            print("[DEBUG] Entering FAST branch (NEW only) with json_path:", json_path)
            
            # ✅ FIXED: Copy matched JSON to temp location to keep sync for future MEMORY
            import shutil
            temp_json_path = "temp_emotion_speaking_mp3.json"
            await asyncio.to_thread(shutil.copy2, json_path, temp_json_path)
            print(f"[DEBUG] Synced {json_path} to {temp_json_path} for future MEMORY")
            
            await asyncio.to_thread(
                fast_thinking_emotion_speech,
                misty_ip=misty_ip,
                json_path=json_path
                # Note: fast_thinking now only supports local audio playback
            )
            return f"NEW task is {main_task} | Similar task found, entering FAST Thinking mode"

        slow_thinking_task = f"Main task: {main_task} | Task details: {curr_task_details}"                     ### 未命中 → SLOW
        print("[DEBUG] slow_thinking_task (NEW fallback SLOW):", slow_thinking_task)
        result = await streaming_slow_thinking_emotion_speech(                                                ### 流式SLOW
            task=slow_thinking_task,
            misty_ip=misty_ip,
            openai_api_key=openai_api_key,
            model_name=thinking_model_name,
            retries=retries
        )
        return (
            f"slow thinking task is {slow_thinking_task} | "
            f"No similar task found in NEW, entering SLOW Thinking mode (streaming) | "
            f"First sentence delay: {(result.get('first_sentence_delay') or 0):.2f}s | "
            f"Current backbone model is {thinking_model_name}"
        )

    ### 5) 常规分支（非 NEW）：永远 SLOW（澄清 + 执行 全部放线程池）
    print("[DEBUG] Entering NON-NEW branch (always SLOW) with task:", task)
    curr_state = await asyncio.to_thread(
        clarify_and_update,
        task,
        openai_api_key=openai_api_key,
        model=model_name
    )                                                                                                          ### 非 NEW 仍需澄清（线程池）
    print("[DEBUG] Current state after clarify_and_update (NON-NEW):", curr_state)

    curr_task = (curr_state.get("task") or "").strip()                                                         ### 取当前任务名
    curr_details = (curr_state.get("details") or "").strip()                                                   ### 取当前细节

    thinking_model_name = await asyncio.to_thread(load_thinking_model_power)                                   ### 读取当前主干模型（线程池）
    slow_thinking_task = f"Main task: {curr_task} | Task details: {curr_details}"                              ### 拼接 SLOW 输入
    print("[DEBUG] slow_thinking_task (NON-NEW always SLOW):", slow_thinking_task)

    result = await streaming_slow_thinking_emotion_speech(                                                     ### 流式SLOW（默认）
        task=slow_thinking_task,
        misty_ip=misty_ip,
        openai_api_key=openai_api_key,
        model_name=thinking_model_name,
        retries=retries
    )
    return (
        f"slow thinking task is {slow_thinking_task} | "
        f"NON-NEW tasks always enter SLOW Thinking mode (streaming) | "
        f"First sentence delay: {result.get('first_sentence_delay', 0):.2f}s | "
        f"Current backbone model is {thinking_model_name}"
    )


def fast_slow_thinking_emotion_speech(
    task: Annotated[
        str,
        ("the task executed by this function")
    ],
) -> str:
    # print("task", task)
    try:
        loop = asyncio.get_running_loop()
        # 如果已经在事件循环中，使用 asyncio.create_task 或直接等待
        # 但因为这是同步函数，需要使用 asyncio.run_coroutine_threadsafe
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(
            fast_slow_thinking_emotion_speech_async(task=task),
            loop
        )
        return future.result()  # 阻塞等待结果
    except RuntimeError:
        # 无 loop，创建新的
        return asyncio.run(
            fast_slow_thinking_emotion_speech_async(task=task)
        )