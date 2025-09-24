# -*- coding: utf-8 -*-
# filename: misty_sensor_som_autogen05.py

import asyncio                                                          ### 事件循环
import os, json                                                         ### 文件/JSON
from typing import Optional, Literal, List, Dict, Any                   ### typing
from pydantic import BaseModel, Field                                   ### 校验

from autogen_core.models import ModelFamily                              ### 模型族
from autogen_core.tools import FunctionTool                              ### 函数→工具
from autogen_ext.models.openai import OpenAIChatCompletionClient         ### OpenAI 客户端

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent, SocietyOfMindAgent  ### Agent 类
from autogen_agentchat.teams import RoundRobinGroupChat                  ### 团队编排
from autogen_agentchat.conditions import TextMentionTermination          ### 终止条件
from autogen_agentchat.ui import Console                                 ### 控制台流式输出

from .SensorRegisterFunction import manage_misty_sensor_tasks             ### 你的底层注册函数



def load_config(config_filename="config.json"):
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
  
cfg = load_config("MistyPilot_config.json")  
misty_ip = cfg["misty_ip"]
openai_api_key = cfg["openai_api_key"]
llm_model = cfg["llm_model"]
stronger_model_name = cfg["stronger_model_name"]
retries = cfg["retries"]
threshold = cfg["threshold"]
cb_json_path = cfg["CB_SUMMARY_JSON_dir"]


# === 控制台输入（给内层 UserProxy 用） ======================================
def console_input(_prompt: str) -> str:                                 ### 输入函数
    try:                                                                ### 容错
        return input('\n[UserProxy] Enter a command (type APPROVE to exit):\n> ')
    except EOFError:                                                    ### EOF 时退出
        return "APPROVE"


# === 任务数据结构（Pydantic） ==============================================
class MistyTask(BaseModel):                                             ### 任务模型
    action: Literal["ADD", "DELETE_ONE", "DELETE_ALL"] = Field(..., description="Type of operation")
    event_type: Optional[Literal["BumpSensor", "TouchSensor"]] = Field(None, description="Event type")
    position: Optional[Literal["bfl","bfr","brl","brr","Chin","Scruff","HeadRight","HeadLeft","HeadBack","HeadFront"]] = Field(None, description="Position")
    callback_file_name: Optional[str] = Field(None, description="Callback file name (must exist in cb_functions_summary.json)")


# === 工具适配器：把结构化入参转为底层 manage_misty_sensor_tasks 的元组表 ============
def misty_sensor_tool_adapter(tasks: List[MistyTask]) -> List[Dict[str, Any]]:  ### 适配器
    tuple_tasks = []                                                    ### 收集元组
    for t in tasks:                                                     ### 遍历任务
        if t.action == "DELETE_ALL":                                    ### 全清理
            tuple_tasks.append(("DELETE_ALL", None, None, None))        ### 规范格式
        else:                                                           ### 其他操作
            tuple_tasks.append((t.action, t.event_type, t.position, t.callback_file_name))
    return manage_misty_sensor_tasks(tuple_tasks)                        ### 调用底层


# === 注册为 FunctionTool（给 LLM 的唯一可调用工具） ==========================
misty_sensor_tool = FunctionTool(                                       ### 工具对象
    misty_sensor_tool_adapter,                                          ### 绑定函数
    name="misty_sensor_tool",                                           ### 工具名（关键）
    description="Register/modify Misty sensor callbacks; always call this for any physical interaction intent."
)


# === Prompt 动态注入回调清单 ================================================
def _normalize_desc(val: Any) -> str:                                   ### 描述清洗
    if val is None:
        return ""
    s = val if isinstance(val, str) else str(val)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in s.split("\n")]
    compact: List[str] = []
    prev_blank = False
    for ln in lines:
        is_blank = (ln == "")
        if is_blank and prev_blank:
            continue
        compact.append(ln)
        prev_blank = is_blank
    return "\n".join(compact).strip()


def build_misty_sensor_agent_prompt(cb_json_path: str) -> str:          ### 构建系统提示
    if not os.path.isfile(cb_json_path):
        raise FileNotFoundError(f"file not found: {cb_json_path}")
    with open(cb_json_path, "r", encoding="utf-8") as f:
        raw_map: Dict[str, Any] = json.load(f)
    if not isinstance(raw_map, dict):
        raise ValueError("top-level JSON must be an object mapping filename -> docs")

    cleaned: Dict[str, str] = {str(k): _normalize_desc(v) for k, v in raw_map.items()}
    registry_json = json.dumps(cleaned, ensure_ascii=False, indent=2, sort_keys=True)

    # 关键修正：明确要求调用“misty_sensor_tool”，而不是底层函数名
    static_body = """You are MistySensorTaskAgent — an agent that only calls the tool.

            Hard Rules
            - On each user input, call the tool exactly once:
              misty_sensor_tool(tasks=[{action,event_type,position,callback_file_name}, ...])
            - Never output free text, explanations, confirmations, Markdown, or JSON.
            - Fixed behavior: Parse user input → Generate structured call → Call the tool. Nothing else is allowed.
            - Even for a single task, it must be inside tasks=[...].
            - Do not reference any previous conversation.

            Actions
            - "ADD": register a sensor event callback
            - "DELETE_ONE": delete a specific sensor event callback
            - "DELETE_ALL": delete all sensor event callbacks (then all other fields must be None)

            Field Constraints
            - event_type ∈ {"BumpSensor","TouchSensor"}
            - position:
              - If BumpSensor: {bfl,bfr,brl,brr}
              - If TouchSensor: {Chin,Scruff,HeadRight,HeadLeft,HeadBack,HeadFront}
            - callback_file_name: MUST be a key in cb_functions_summary.json
            - When action="DELETE_ALL": event_type=position=callback_file_name=None

            Callback Selection (STRICT)
            1) Use ONLY callback_file_name keys listed in the Callback Registry below. Do NOT invent keys.
            2) Description matching first (English/Chinese). Prefer the most specific callback if multiple match.
            3) Position consistency: head → TouchSensor; feet/wheels/collision → BumpSensor.
            4) If uncertain, choose the more specific/single-purpose callback.

            Event Type Inference (STRICT but with fallback reasoning)
            - Always follow this reasoning order:
              1) First, scan the user text for explicit body-part or sensor position words.
                - If a match is found, LOCK that position. Do not override later.
              2) If no explicit match, interpret descriptive phrases or synonyms (see below).
              3) If still unclear, make a reasoned guess based on context (emotion, greeting, action).
                - For greetings, prefer HeadFront.
                - For photo-taking, prefer Chin (simulate looking up).
                - For emotions without explicit location, prefer HeadFront (default touch).
                - For collision-related words, prefer bfl (left front bumper) as default.
              4) Only if none apply, choose the safest single default:
                - Touch context → HeadFront
                - Bump context → bfl

            - BumpSensor (lower body/feet/wheels/collision):
              - left front → bfl
              - right front → bfr
              - left rear → brl
              - right rear → brr
              - if user says bfl/bfr/brl/brr directly, use it as is

            - TouchSensor (head touch):
              - "Chin", "under chin", "under jaw" → Chin
              - "Scruff", "back of neck", "nape" → Scruff
              - "right side of head", "right ear side" → HeadRight
              - "left side of head", "left ear side" → HeadLeft
              - "back of head", "back head" → HeadBack
              - "forehead", "front of head" → HeadFront
              - if user says one directly, use it as is

            - Reasoning Reminder:
              Each time you infer a position, implicitly THINK:
                “Did the user specify a body part? If not, which default guess fits the action best?”

          Multi-task Strategy (HARD)
- Clause Segmentation:
  - Split the user input by semicolons (';','；'), periods ('.','。'), and commas (',','，').
  - Semicolons are HARD boundaries: each semicolon-delimited part is a separate clause.
  - Periods are HARD boundaries as well.
  - Commas are SOFT boundaries: form a new clause only if the comma segment introduces a new trigger/action/position cue
    (e.g., contains "and/then/also/oh and/if/when" or equivalent Chinese connectives).
  - Preserve the original order; drop empty clauses.

- One Clause → One Task (1:1 mapping):
  - Each actionable clause MUST yield exactly one task inside tasks=[...].
  - Non-actionable clauses (no trigger, no position, no allowed keywords) produce no task.

- Per-Clause Reasoning Order (HARD, no cross-clause borrowing):
  1) LOCK position from THIS CLAUSE using Position Synonyms. Once locked, never override due to callback choice.
  2) Infer event_type from the locked position (Head* → TouchSensor; b*f* → BumpSensor).
  3) Select callback ONLY by keyword gating found in THIS CLAUSE (see Callback Keyword Gates).
  4) Fallback (THIS CLAUSE ONLY, last resort):
     - Touch-like with no explicit position/keywords → HeadFront (no greeting/photo unless gated).
     - Bump-like with no explicit position/keywords → bfl.
     - Never output “hello/photo/emotion” without matching keywords in THIS CLAUSE.
  5) Compose exactly one task for this clause or skip if non-actionable.

- Cross-Clause Isolation (HARD):
  - Do NOT reuse positions or keywords from other clauses.
  - Do NOT merge two clauses into one task.
  - Do NOT let a callback choice in one clause change the position/event_type of another clause.

- Conflict & Dedup Rules:
  - If multiple clauses target the SAME (event_type, position) with DIFFERENT callbacks, keep the LAST-mentioned clause (last-wins).
  - If two tasks are identical, keep only one (deduplicate).
  - All callback_file_name MUST exist in the runtime-injected Callback Registry.

            Output Requirement
            - The ONLY output is a single call:
              misty_sensor_tool(tasks=[...])
            - Strictly follow the function signature. No extra characters.

            Callback Registry (runtime-injected; DO NOT hallucinate keys)
            ```json
    """
    return static_body + registry_json + "\n```\n"


# === 模型客户端（内层工具 Agent 用） ========================================
misty_sensor_model_client = OpenAIChatCompletionClient(                ### 工具 Agent 模型
    model=llm_model,
    api_key=openai_api_key,
    model_info={
        "vision": False,
        "function_calling": True,                                      ### 必须：允许工具调用
        "json_output": False,
        "family": ModelFamily.GPT_5,
    },
)

# === 构造工具型 Agent（内层） ==============================================
MistySensorAgent_prompt = build_misty_sensor_agent_prompt(cb_json_path)  ### 动态注入回调清单

MistySensorAgent = AssistantAgent(                                      ### 工具型 Agent
    name="MistySensorAgent",
    description="Handle Misty sensor interactions by generating a single structured tool call.",
    model_client=misty_sensor_model_client,
    tools=[misty_sensor_tool],
    system_message=MistySensorAgent_prompt,                              ### 只允许函数调用
)

# === 内层 UserProxy（用于人工输入/停止） ====================================
MistySensorAgent_UserProxy = UserProxyAgent(                            ### 人类操作者
    name="UserProxy",
    description="Human operator. Type 'APPROVE' to stop.",
    input_func=console_input,
)

# === 内层团队（RoundRobin：User ↔ ToolAgent；输入“APPROVE”终止） =============
sensor_inner_stop = TextMentionTermination("APPROVE")                   ### 终止口令
misty_sensor_inner_team = RoundRobinGroupChat(                          ### 内层团队
    [MistySensorAgent, MistySensorAgent_UserProxy],
    termination_condition=sensor_inner_stop,
    max_turns=100,
)

# === 外层 SOM Agent（把内层团队“打包成一个 Agent”） =========================
sensor_group_model_client = OpenAIChatCompletionClient(                 ### SOM 外层模型
    model=llm_model,                                                    ### 轻量模型即可
    api_key=openai_api_key,
    model_info={
        "vision": False,
        "json_output": False,
        "function_calling": False,                                      ### SOM 本身不用调工具
        "family": ModelFamily.GPT_5,
    },
)

MistySensorAgent_SOM = SocietyOfMindAgent(                              ### SOM 封装
    name="MistySensorAgent_SOM",
    team=misty_sensor_inner_team,
    model_client=sensor_group_model_client,
    description="Society-of-Mind wrapper for Misty sensor control: routes human input to the inner tool-only agent.",
    instruction="You must ONLY **TERMINATE** and nothing else.",        ### 外层只负责结束
)

