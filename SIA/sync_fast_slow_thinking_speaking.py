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
from .sync_misty_slow_thinking_emotion_speech import slow_thinking_emotion_speech_sync### SLOW 分支（同步）
from .misty_speaking_action_memory import (                                           ### 向量库（同步）
    init_client, get_or_create_collection, upsert_texts, query_emotion_action_speak_task
)
from .task_memory_action_utils import (                                               ### 文件/状态（同步）
 archive_temp_mp3_json
)
from .sync_curr_task_set import clarify_and_update, load_state, reset_state
from .fast_slow_thinking_state import load_thinking_model_power, update_thinking_model_power
# ↑ 注意：不再使用 reset_thinking_model_power，以免签名不一致

# ### 路径处理
# CFG_PATH = Path(__file__).resolve().with_name("misty_config.json")     ### 配置文件路径
# _CFG_CACHE = None                                                      ### 进程级缓存

# def _load_cfg() -> dict:
#     """最小配置加载：一次读取，后续复用。"""
#     global _CFG_CACHE
#     if _CFG_CACHE is not None:
#         return _CFG_CACHE
#     data = json.loads(CFG_PATH.read_text(encoding="utf-8"))
#     # —— 简单校验（必要项）——
#     if not data.get("openai_api_key"):
#         raise RuntimeError("openai_api_key 未设置（misty_config.json）")
#     if not data.get("misty_ip"):
#         raise RuntimeError("misty_ip 未设置（misty_config.json）")
#     _CFG_CACHE = data
#     return _CFG_CACHE



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
        try:
            res = asyncio.run(coro)
            q.put((True, res))
        except Exception as e:
            q.put((False, e))

    t = threading.Thread(target=_runner, name="isolated_asyncio_runner", daemon=True)
    t.start()
    ok, val = q.get()
    if ok:
        return val
    raise val



async def fast_slow_thinking_emotion_speech_async(
    task: Annotated[
        str,
        ("the task executed by this function")
    ],
) -> str:
    ### 1) 配置与向量库（全部放入线程池避免阻塞事件循环）
    cfg = await asyncio.to_thread(load_config)                                                                 ### 读取并缓存配置（文件 I/O）
    print("[DEBUG] Loaded config:", cfg)

    misty_ip = cfg["misty_ip"]                                                                               ### 取 Misty IP
    openai_api_key = cfg["openai_api_key"]                                                                   ### 取 OpenAI Key
    model_name = cfg.get("llm_model", "gpt-5-nano-2025-08-07")                                               ### 基础澄清模型
    retries = int(cfg.get("retries", 1))                                                                      ### 重试次数
    threshold = float(cfg.get("threshold", 0.2))                                                              ### 向量检索阈值
    store_dir = cfg.get("store_dir", "./misty_emotion_action_speaking_store")                                 ### 向量库存储目录
    collection = cfg.get("collection", "text-embedding-3-large")                                              ### 向量集合名
    base_model = cfg.get("llm_model", "gpt-5-nano-2025-08-07")                                                ### 基础主干模型
    powerful_model = cfg.get("stronger_model_name", "gpt-5-2025-08-07")                                       ### 升级主干模型

    print(f"[DEBUG] misty_ip={misty_ip}, model_name={model_name}, retries={retries}, threshold={threshold}")
    print(f"[DEBUG] store_dir={store_dir}, collection={collection}")

    client = await asyncio.to_thread(init_client, store_dir)                                                  ### 初始化向量库客户端（可能做磁盘 I/O）
    print("[DEBUG] Vector DB client initialized:", client)
    col = await asyncio.to_thread(get_or_create_collection, client, name=collection)                          ### 获取/创建集合（可能触发 I/O）
    print("[DEBUG] Collection ready:", col)

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
        await asyncio.to_thread(                                                                              ### 用 SLOW 复跑上次任务（同步外壳放线程）
            slow_thinking_emotion_speech_sync,
            slow_thinking_task, misty_ip, openai_api_key, thinking_model_name, retries
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
        await asyncio.to_thread(upsert_texts, col, texts=prev_task, paths=new_file_path)                      ### 向量库入库（I/O）
        print("[DEBUG] Upsert completed for MEMORY task")
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
            await asyncio.to_thread(
                fast_thinking_emotion_speech,
                misty_ip=misty_ip,
                json_path=json_path
            )
            return f"NEW task is {main_task} | Similar task found, entering FAST Thinking mode"

        slow_thinking_task = f"Main task: {main_task} | Task details: {curr_task_details}"                     ### 未命中 → SLOW
        print("[DEBUG] slow_thinking_task (NEW fallback SLOW):", slow_thinking_task)
        await asyncio.to_thread(
            slow_thinking_emotion_speech_sync,
            slow_thinking_task, misty_ip, openai_api_key, thinking_model_name, retries
        )
        return (
            f"slow thinking task is {slow_thinking_task} | "
            f"No similar task found in NEW, entering SLOW Thinking mode | "
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

    await asyncio.to_thread(
        slow_thinking_emotion_speech_sync,
        slow_thinking_task, misty_ip, openai_api_key, thinking_model_name, retries
    )                                                                                                          ### 执行 SLOW（线程池）
    return (
        f"slow thinking task is {slow_thinking_task} | "
        f"NON-NEW tasks always enter SLOW Thinking mode | "
        f"Current backbone model is {thinking_model_name}"
    )


def fast_slow_thinking_emotion_speech(
    task: Annotated[
        str,
        ("the task executed by this function")
    ]
) -> str:
    # print("task", task)
    try:
        asyncio.get_running_loop()  # 有 loop
        return _run_coro_in_new_loop_sync(
            fast_slow_thinking_emotion_speech_async(task=task)
        )
    except RuntimeError:
        # 无 loop
        return asyncio.run(
            fast_slow_thinking_emotion_speech_async(task=task)
        )

