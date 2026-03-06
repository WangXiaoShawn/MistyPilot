
# -*- coding: utf-8 -*- # summary_agent.py - 维护状态并记录 clarify 使用的模型名（clarify_model）
import asyncio
import threading
import queue
import weakref
from typing import Optional, Any
import re, json
import os
from pydantic import BaseModel, ValidationError, field_validator, ConfigDict
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelFamily

STATE_FILE = "misty_speaking_action_state.json"

# ===== System Prompt（保持不变：模型只产出 task/details 两键） =====
SYSTEM_PROMPT = """
You are a **task state** maintenance expert. You will receive the **CURRENT task state** and an **OPERATION**.
You will receive **Current Task State:** and **Current Operation:**

Update the **taskstate** strictly according to the rules below and return ONLY ONE JSON object with EXACTLY the two keys:
{
  "task": "<current task>",
  "details": "<semicolon-separated details or empty string>"
}
No Markdown, no comments, no extra fields.

Operation types and rules:

1) If the CURRENT task state is empty (task = "" and details = ""), this means it is a new task.
- You must treat the input as creating a new task, equivalent to executing a NEW operation.
- Set "task" = the task from the input (one concise sentence).
- Set "details" = the details from the input; if no details are provided, set "details" = "".

2) NEW <task> <details>
- Create a new task.
- Set "task" = <task> (one concise sentence).
- REPLACE all previous details with <details>. Do not keep any prior details.
- If <details> is empty or missing, set "details" = "".

3) UPDATE <details>
- Update details of the EXISTING task.
- "task" MUST NOT be modified.
- Use <details> to ADD or REPLACE items in the current "details".
- Semantic handling REQUIRED: you DO NOT need exact string match; infer which existing item is equivalent or conflicting and replace it. If it's new, add it.
- Resolve duplicates/conflicts by keeping ONLY the latest version.
- Keep details unique, clean, and semicolon-separated.

4) DELETE <details>
- Remove one or more items from the current "details".
- Semantic handling REQUIRED: you DO NOT need exact string match; infer which item(s) best match the intent and delete them.
- After deletion, the remaining details must stay clean, concise, and semicolon-separated.
- If no reasonable match exists, leave details unchanged.

Additional rules:
- If the operation is invalid or it's unclear how to modify, keep BOTH "task" and "details" unchanged.
- "task" is always a single concise description and cannot be changed (EXCEPT in NEW).
- "details" is ALWAYS a single string. Items are separated by semicolons ";".
If empty, output "".
- Output MUST be a single JSON object with EXACTLY the two keys "task" and "details".
"""

# ===== Pydantic：保持两键校验不变 =====
class TaskStateOutput(BaseModel):
    task: str
    details: str
    model_config = ConfigDict(extra="forbid")

    @field_validator("task")
    @classmethod
    def _task_one_line_non_empty(cls, v: str) -> str:
        s = " ".join((v or "").split())
        if not s:
            raise ValueError("task must be non-empty")
        return s

    @field_validator("details")
    @classmethod
    def _details_string(cls, v: str) -> str:
        if v is None:
            return ""
        s = " ".join(str(v).split())
        return s

# ===== JSON提取（不变） =====
CODE_FENCE_RE = re.compile(r"^```[\w-]*\s*|\s*```$", re.IGNORECASE)


def _extract_json_object_text(raw: str) -> str:
    txt = CODE_FENCE_RE.sub("", (raw or "").strip())
    if txt.startswith("{") and txt.endswith("}"):
        return txt
    l = txt.find("{")
    r = txt.rfind("}")
    if l != -1 and r != -1 and l < r:
        cand = txt[l:r+1]
        if re.match(r"^\s*\{", cand):
            return cand
    return txt

# ===== 客户端缓存（不变） =====
_client_cache = {}
_client_refs = weakref.WeakValueDictionary()

def _get_cached_client(api_key: str, model: str) -> OpenAIChatCompletionClient:
    cache_key = f"{api_key[:10]}_{model}"
    if cache_key in _client_cache:
        return _client_cache[cache_key]
    client = OpenAIChatCompletionClient(
        model=model, 
        api_key=api_key,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": ModelFamily.GPT_5,
        }
    )
    _client_cache[cache_key] = client
    return client

# ===== 运行并解析（不变） =====
async def _run_with_schema(agent: AssistantAgent, task: str, retries: int = 2) -> TaskStateOutput:
    last_err: Optional[str] = None
    cur_task = task
    for attempt in range(retries + 1):
        result = await agent.run(task=cur_task)
        content = result.messages[-1].content
        if isinstance(content, list):
            content = "".join(
                (p.get("text") or p.get("content") or "") if isinstance(p, dict) else str(p)
                for p in content
            )
        try:
            json_text = _extract_json_object_text(str(content))
            data = json.loads(json_text)
            if not isinstance(data, dict):
                raise TypeError("Output is not a JSON object.")
            parsed = TaskStateOutput.model_validate(data)
            return parsed
        except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as e:
            last_err = str(e)
            if attempt < retries:
                cur_task = (
                    "Your previous output did NOT match the REQUIRED JSON schema.\n"
                    f"Error: {last_err}\n\n"
                    "Return ONLY ONE JSON object with EXACTLY these keys and NOTHING ELSE:\n"
                    ' - "task": non-empty single-line string\n'
                    ' - "details": single-line string (may be empty "")\n'
                    "No extra keys, no comments, no prose, no code fences, no trailing commas.\n"
                    "Remember the rules: NEW <task> <details> replaces all details; "
                    "UPDATE <details> adds/replaces semantically; DELETE <details> removes semantically."
                )
                continue
            raise RuntimeError(f"Failed after {retries} retries. Last error:\n{last_err}")

# ===== 工具：保证状态字典包含三键 =====
def _ensure_state_schema(state: dict) -> dict:
    """补齐缺失键，只保留 task 和 details。"""
    if not isinstance(state, dict):
        state = {}
    state.setdefault("task", "")
    state.setdefault("details", "")
    return state

# ===== 异步 clarify =====
async def clarify_async(
    user_description: str,
    openai_api_key: str,
    model: str = "gpt-5-nano",
    retries: int = 2
) -> dict:
    model_client = _get_cached_client(openai_api_key, model)
    agent = AssistantAgent(
        name="TaskStateMaintainer",
        model_client=model_client,
        system_message=SYSTEM_PROMPT,
    )
    result_obj = await _run_with_schema(agent, task=user_description, retries=retries)
    return result_obj.model_dump()

# ===== 在线程里跑协程（不变） =====
def _run_coro_in_thread(coro) -> Any:
    result_queue = queue.Queue()
    def thread_worker():
        try:
            result = asyncio.run(coro)
            result_queue.put(("success", result))
        except Exception as e:
            result_queue.put(("error", e))
    thread = threading.Thread(target=thread_worker, daemon=True)
    thread.start()
    thread.join(timeout=60)
    if thread.is_alive():
        raise TimeoutError("Operation timed out")
    status, value = result_queue.get_nowait()
    if status == "success":
        return value
    else:
        raise value

# ===== 同步 clarify：同样注入 clarify_model =====
def clarify(
    user_description: str,
    openai_api_key: str,
    model: str = "gpt-5-nano",
    retries: int = 2
) -> dict:
    coro = clarify_async(
        user_description=user_description,
        openai_api_key=openai_api_key,
        model=model,
        retries=retries
    )
    return _run_coro_in_thread(coro)

def load_state() -> dict:
    """Load current task state; 自动补齐两键结构。"""
    if not os.path.exists(STATE_FILE):
        state = _ensure_state_schema({"task": "", "details": ""})
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return state
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _ensure_state_schema(raw)

def save_state(state: dict):
    """Save task state (只含 task 和 details)。"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(_ensure_state_schema(state), f, ensure_ascii=False, indent=2)

def clarify_and_update(user_input: str, openai_api_key: str, model: str = "gpt-5-nano") -> dict:
    """
    读取状态 -> 调用 clarify -> 保存状态
    """
    current_state = load_state()
    merged_input = f"Current state: {json.dumps(current_state, ensure_ascii=False)}\nOperation: {user_input}"
    new_state = clarify(
        user_description=merged_input,
        openai_api_key=openai_api_key,
        model=model,
    )
    if not isinstance(new_state, dict):
        try:
            new_state = dict(new_state)
        except Exception:
            raise TypeError("clarify() must return a dict with keys 'task' and 'details'")
    # 补齐 schema 并保存
    new_state = _ensure_state_schema(new_state)
    save_state(new_state)
    return new_state

def reset_state():
    """将状态重置为空。"""
    save_state({"task": "", "details": ""})
    print("\n[State reset] ->", load_state())

