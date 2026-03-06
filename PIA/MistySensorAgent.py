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

from .SensorRegisterFunction import manage_misty_sensor_tasks  
from .Misty_Callback_Executor import execute_from_cb_summary  ### 导入立即执行函数

# Import voice input queue for interactive communication
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from voice_input_queue import voice_input_func


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


# === 用户输入函数 ============================================================
# Using voice_input_func from voice_input_queue module for voice-based interaction
# This allows the system to receive transcribed voice input during task execution
# The voice input system automatically handles:
#   - Waiting for voice input when UserProxy needs interaction
#   - Converting speech to text via faster-whisper
#   - Routing transcribed text to the appropriate agent

# Legacy console_input kept for reference (not used)
def console_input(_prompt: str) -> str:                                 ### 输入函数（已弃用）
    try:                                                                ### 容错
        return input('\n[UserProxy] Enter a command (type APPROVE to exit):\n> ')
    except EOFError:                                                    ### EOF 时退出
        return "APPROVE"


# === 任务数据结构（Pydantic） ==============================================
class MistyTask(BaseModel):                                             ### 任务模型
    action: Literal["ADD", "DELETE_ONE", "DELETE_ALL", "EXECUTE_NOW"] = Field(..., description="Type of operation")
    event_type: Optional[Literal["BumpSensor", "TouchSensor", "OneTimeCall"]] = Field(None, description="Event type")
    position: Optional[Literal["bfl","bfr","brl","brr","Chin","Scruff","HeadRight","HeadLeft","HeadBack","HeadFront"]] = Field(None, description="Position")
    callback_file_name: Optional[str] = Field(None, description="Callback file name (must exist in cb_functions_summary.json)")


# === 工具适配器：把结构化入参转为底层 manage_misty_sensor_tasks 的元组表 ============
def misty_sensor_tool_adapter(tasks: List[MistyTask]) -> List[Dict[str, Any]]:  ### 适配器
    results = []                                                        ### 收集结果
    tuple_tasks = []                                                    ### 收集元组任务
    
    for t in tasks:                                                     ### 遍历任务
        if t.action == "EXECUTE_NOW":                                   ### 立即执行
            try:
                result = execute_from_cb_summary(
                    callback_file_name=t.callback_file_name,
                    event_data={},
                    misty_ip=None,  # 从配置文件读取
                    api_key=None
                )
                results.append({
                    "action": "EXECUTE_NOW",
                    "status": "success",
                    "callback_file_name": t.callback_file_name,
                    "message": f"Immediately executed {t.callback_file_name}"
                })
            except Exception as e:
                results.append({
                    "action": "EXECUTE_NOW",
                    "status": "error",
                    "callback_file_name": t.callback_file_name,
                    "error": str(e)
                })
        elif t.action == "DELETE_ALL":                                  ### 全清理
            tuple_tasks.append(("DELETE_ALL", None, None, None))        ### 规范格式
        else:                                                           ### 其他操作
            tuple_tasks.append((t.action, t.event_type, t.position, t.callback_file_name))
    
    # 如果有需要通过底层处理的任务，调用原函数
    if tuple_tasks:
        sensor_results = manage_misty_sensor_tasks(tuple_tasks)
        results.extend(sensor_results)
    
    return results if results else [{"status": "no_action"}]            ### 返回结果


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

    static_body = """
# System Prompt: MistySensorTaskAgent

You are **MistySensorTaskAgent**, a dedicated tool-calling agent for Misty robot physical interactions. Your sole purpose is to convert user requests into structured sensor tasks.

========================
CORE ROLE
========================
1) Decide which physical interaction tasks to generate based on user input.
2) Output ONLY a single call to `misty_sensor_tool`.
3) NEVER output explanations, Markdown prose, or free text.

========================
TOOL SIGNATURE
========================
misty_sensor_tool(tasks=[{"action": str, "event_type": str, "position": str, "callback_file_name": str}])

========================
FIELD CONSTRAINTS (HARD)
========================
- action: ADD, DELETE_ONE, DELETE_ALL, EXECUTE_NOW
- event_type: BumpSensor, TouchSensor, OneTimeCall, or None (only for DELETE_ALL)
- position:
  - If BumpSensor: {bfl, bfr, brl, brr}
  - If TouchSensor: {Chin, Scruff, HeadRight, HeadLeft, HeadBack, HeadFront}
  - If OneTimeCall or DELETE_ALL: None (MUST be None)
- callback_file_name: MUST be a key in the injected Callback Registry. DO NOT invent keys.

========================
ACTION DECISION LOGIC (WHEN TO USE)
========================
1. DELETE_ALL: 
   - User wants to clear/remove all sensor mappings (e.g., "clear all", "删除所有").
2. DELETE_ONE: 
   - User wants to remove a specific mapping (e.g., "delete the touch trigger").
3. EXECUTE_NOW: 
   - Trigger: User requests immediate action (e.g., "now", "immediately", "马上", "立即").
   - Implicit Trigger: User mentions an emotion/action (found in Registry) but provides NO sensor position and NO trigger words (like "when/if").
   - Constraint: action="EXECUTE_NOW", event_type="OneTimeCall", position=None.
4. ADD:
   - Trigger: User provides a specific sensor position/body part (e.g., "head", "chin", "bumper").
   - Trigger: User uses conditional wording (e.g., "when", "if", "whenever", "当...时", "如果...就").
   - Constraint: Infer event_type from the position.

========================
INFERENCE ENGINE (PER-CLAUSE)
========================
1. SEGMENTATION: Split input by (;, 。, ., ,) where commas introduce a new trigger/action.
2. POSITION LOCK: 
   - Bump Synonyms: Left front -> bfl; Right front -> bfr; Left rear -> brl; Right rear -> brr.
   - Touch Synonyms: Chin (下巴), Scruff (后颈), HeadRight (右侧头), HeadLeft (左侧头), HeadBack (后脑勺), HeadFront (额头/forehead).
   - Defaulting: If context is touch-like -> HeadFront; Collision-like -> bfl.
3. EVENT TYPE DETERMINATION: 
   - If action is EXECUTE_NOW -> OneTimeCall.
   - If position is Head*/Chin/Scruff -> TouchSensor.
   - If position is b* -> BumpSensor.
4. CALLBACK SELECTION: 
   - Match keywords against the Registry descriptions.
   - CRITICAL: If NO callback match is found for a clause, SKIP that clause (no task).

========================
MULTI-TASK & ISOLATION (HARD)
========================
- CROSS-CLAUSE ISOLATION: Do NOT reuse positions or keywords across clauses.
- ONE CLAUSE -> ONE TASK: Each actionable segment yields exactly one task.
- LAST-WINS: If multiple clauses target the same (event_type, position), keep only the last mentioned.
- DEDUPLICATE: Remove identical tasks within the same tool call.

========================
CALLBACK REGISTRY (Runtime Injected)
========================
<INSERT_JSON_REGISTRY_HERE>

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


MistySensorAgent_UserProxy = UserProxyAgent(
    name="UserProxy",
    description="Voice-enabled user proxy for interactive task execution.",
    input_func=voice_input_func,  # Voice input for seamless interaction
)

sensor_inner_stop = TextMentionTermination("APPROVE")                   ### 终止口令
misty_sensor_inner_team = RoundRobinGroupChat(                          ### 内层团队
    [MistySensorAgent, MistySensorAgent_UserProxy],
    termination_condition=sensor_inner_stop,
    max_turns=10,
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

# === Factory function for creating fresh agent instances =====================
def create_misty_sensor_agent():
    """
    Factory function to create a fresh MistySensorAgent_SOM instance
    Call this for each new task to avoid memory accumulation
    """
    # Rebuild prompt with latest callback data
    prompt = build_misty_sensor_agent_prompt(cb_json_path)
    
    # Create inner assistant agent
    agent = AssistantAgent(
        name="MistySensorAgent",
        description="Handle Misty sensor interactions by generating a single structured tool call.",
        model_client=misty_sensor_model_client,
        tools=[misty_sensor_tool],
        system_message=prompt,
    )
    
    # Create inner user proxy
    user_proxy = UserProxyAgent(
        name="UserProxy",
        description="Voice-enabled user proxy for interactive task execution.",
        input_func=voice_input_func,
    )
    
    # Create inner team
    inner_stop = TextMentionTermination("APPROVE")
    inner_team = RoundRobinGroupChat(
        [agent, user_proxy],
        termination_condition=inner_stop,
        max_turns=10,
    )
    
    # Create SOM wrapper
    som_agent = SocietyOfMindAgent(
        name="MistySensorAgent_SOM",
        team=inner_team,
        description="Handle all Misty physical sensor interactions and non-verbal commands; manages touch sensors, bump sensors, and immediate callback executions.",
        instruction="""When you see APPROVE, you must ONLY output TERMINATE and nothing else.""",
    )
    
    return som_agent

# === Legacy module-level instance (for backward compatibility) ===============
MistySensorAgent_SOM = SocietyOfMindAgent(
    name="MistySensorAgent_SOM",
    team=misty_sensor_inner_team,
    description="Handle all Misty physical sensor interactions and non-verbal commands; manages touch sensors, bump sensors, and immediate callback executions.",
    instruction="""When you see APPROVE, you must ONLY output TERMINATE and nothing else.""",
)

