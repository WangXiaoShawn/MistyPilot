# -*- coding: utf-8 -*-
# filename: test_misty_tool_autogen05.py

import asyncio                                                      ### 事件循环
from autogen_agentchat.agents import AssistantAgent                 ### AutoGen 0.5+ Agent
from autogen_core.tools import FunctionTool                         ### 函数→工具包装
from autogen_core.models import ModelFamily                         ### 模型族（能力声明）
from autogen_ext.models.openai import OpenAIChatCompletionClient    ### OpenAI兼容客户端
from autogen_agentchat.agents import UserProxyAgent, SocietyOfMindAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from .sync_fast_slow_thinking_speaking import fast_slow_thinking_emotion_speech
from autogen_agentchat.ui import Console
import os
import json
import sys

# Import voice input queue for interactive communication
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from voice_input_queue import voice_input_func


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

cfg = load_config("MistyPilot_config.json")   # 默认就在上一层目录
misty_ip = cfg["misty_ip"]
openai_api_key = cfg["openai_api_key"]
llm_model = cfg["llm_model"]
stronger_model_name = cfg["stronger_model_name"]
retries = cfg["retries"]
threshold = cfg["threshold"]


# === 1) 定义带提示的输入函数（替代内置 input） ==========================
def console_input(_prompt: str) -> str:
    try:
        return input('\n[UserProxy] Enter a command (type APPROVE to exit):\n> ')
    except EOFError:
        return "APPROVE"

# ===== 注册为工具（生成 schema 发给模型；强制 function_calling） =====================
mistyemotionspeaking_tool = FunctionTool(
    fast_slow_thinking_emotion_speech,                                                                       ### 指向薄包装
    name="mistyemotionspeaking_tool",                                         ### 工具名（与你原函数一致）
    description=(
      "Single, tool-only entry point for Misty’s voice tasks: if the request can be fulfilled by speech alone, issue exactly one call to this function."
    ),                                                                               
)

MistyEmotionSpeakingAgent_SYSTEM_PROMPT = """
You are MistyEmotionSpeakingAgent — a **tool-only** agent. 
Your sole function is to parse user intent into a precise one-line command and execute the tool call.

---

### 1. TOOL USAGE
You have ONE tool. You MUST call this tool for every valid turn:
- `mistyemotionspeaking_tool(task="<one-line-command>")`

---

### 2. OUTPUT CONSTRAINTS
- **STRICT FORMAT:** Output ONLY the tool call. No free text, no thinking process, no explanations, no Markdown code blocks in the response.
- **LANGUAGE:** English only. If the user input is not English, translate the intent internally and output the final command in English.
<update>
- **CONTEXT AWARENESS:** Refer to the conversation history to determine if the input is a continuation of the current task or a switch to a new topic.
</update>
---

### 3. COMMAND PARSING RULES (THE ONE-LINE COMMAND)
The `task` parameter must be exactly one of the following six actions:

#### A. Single-Word Actions (High Priority)
- **UPGRADE**: Explicit request to enhance/boost/increase capability.
- **DOWNGRADE**: Explicit request to lower/reduce/decrease capability.
- **MEMORY**: Request to "remember this", "save to memory", or the standalone word "MEM".
*Priority:* If a message contains one of these AND another intent, output ONLY the single-word action.

#### B. Parameter Actions
- **NEW_main:<main_task>  details:<details>**
  - Use for the **first message**, or when the user says "new task/start over/begin".
<update>
  - **TOPIC SWITCH:** Use if the user introduces a new core object (e.g., from 'dragon' to 'robot'), a different action (e.g., from 'story' to 'poem'), or a complete independent thought that does not logically build upon the immediate previous intent.
</update>
  - **Note:** Must have **EXACTLY TWO SPACES** before `details:`.
- **UPDATE_details:<details>**
  - Use when the user provides more context, cause, or updates for the **same** situation/task. DO NOT modify the `main_task`.
- **DELETE_details:<details_to_remove>**
  - Use when the user wants to remove or disable specific previously mentioned details.

---

### 4. FIELD CONSTRUCTION RULES

**[main_task] (For NEW only)**
- English imperative; ≤ 12 words; **no trailing period**.
- Keep the core action AND the task identity (the object). NEVER move the task object (e.g., story name) to `details`.
- **REMOVAL RULE:** Remove trailing phrases introduced by: *with, using, in, for, by, featuring, as, against, via, through, under, without, between, across, over*.

**[details]**
- English; semicolon-separated items; **no trailing period**.
- Modifiers only (tone, style, persona, audience, length, format, ending, etc.).
- If no modifiers exist, the field must still appear (e.g., `details:`).

---

### 5. STATE & FALLBACK
- **FIRST MESSAGE:** Must be `NEW_main`. Ignore UPGRADE/DOWNGRADE/MEMORY triggers.
- **STATE CONTINUATION:** If the message adds background or clarification to the current situation, use `UPDATE_details`.
<update>
- **AMBIGUITY RULE:** If the input is a complete standalone request rather than a modifier (e.g., "Tell a joke" instead of "Make it funny"), prioritize `NEW_main` to ensure a clean topic break.
</update>
- **FALLBACK:** If no rules match and it's not a first message, output: `UPDATE_details: None`

---

### 6. EXAMPLES (FOR INTERNAL LOGIC ONLY)
- *User:* "Tell a story about a dragon in a brave tone."
  -> `mistyemotionspeaking_tool(task="NEW_main:Tell a story about a dragon  details:tone brave")`
- *User:* "Actually, make the ending sad."
  -> `mistyemotionspeaking_tool(task="UPDATE_details:ending sad")`
<update>
- *User:* "Now write a poem about the moon."
  -> `mistyemotionspeaking_tool(task="NEW_main:Write a poem about the moon  details:")`
</update>
- *User:* "Stop using the brave tone."
  -> `mistyemotionspeaking_tool(task="DELETE_details:tone brave")`
- *User:* "Please remember this result."
  -> `mistyemotionspeaking_tool(task="MEMORY")`

---
**FINAL MANDATE:** Execute the tool call now. Any other output is an absolute failure.
"""


# ===== 创建模型客户端 =============================================

# 根据模型类型判断 family
if "gpt-5" in llm_model.lower():
    model_family = ModelFamily.GPT_5
elif "gpt-4" in llm_model.lower():
    model_family = ModelFamily.GPT_4O
else:
    model_family = ModelFamily.UNKNOWN

# 用于 SocietyOfMind 内部选择 agent
emotion_speaking_group_model_client = OpenAIChatCompletionClient(
    model=llm_model,
    api_key=openai_api_key,
    model_info={
        "vision": False,
        "json_output": False,
        "function_calling": False,  
        "family": model_family,
        "structured_output": False,
    },
)

# 用于执行实际任务（支持函数调用）
misty_emotion_speaking_model_client = OpenAIChatCompletionClient(
    model=llm_model,
    api_key=openai_api_key,
    model_info={
        "vision": False,
        "function_calling": True,
        "json_output": False,
        "family": model_family,
        "structured_output": False,
    }
)



# ===== 直接构造 Agent（你要的"只有一个 agent"） ============================
def create_misty_emotion_speaking_agent():
    """
    Factory function to create a fresh MistyEmotionSpeakingAgent_SOM instance
    Call this for each new task to avoid memory accumulation
    """
    # Create inner assistant agent
    agent = AssistantAgent(
        name="MistyEmotionSpeakingAgent",
        description = "Enables the Misty robot to handle voice interactions and emotional expression through natural conversation.", 
        model_client=misty_emotion_speaking_model_client,
        tools=[mistyemotionspeaking_tool],
        system_message=MistyEmotionSpeakingAgent_SYSTEM_PROMPT,
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
        max_turns=100
    )
    
    # Create SOM wrapper
    som_agent = SocietyOfMindAgent(
        name="MistyEmotionSpeakingAgent_SOM",
        team=inner_team,
        description="Execute all Misty commands solvable by speech; any speech-executable command must be handled by this agent.",
        instruction="Output exactly: TERMINATE",
    )
    
    return som_agent

# Legacy: Keep module-level instance for backward compatibility
# (will be replaced by factory function in MistyPilot_with_voice.py)
MistyEmotionSpeakingAgent = AssistantAgent(
    name="MistyEmotionSpeakingAgent",
    description = "Enables the Misty robot to handle voice interactions and emotional expression through natural conversation.", 
    model_client=misty_emotion_speaking_model_client,
    tools=[mistyemotionspeaking_tool],
    system_message=MistyEmotionSpeakingAgent_SYSTEM_PROMPT,
)

# === 内层 UserProxy（用于语音交互） =========================================
# Uses voice_input_func to enable voice-based interaction during task execution
# When this agent needs user input:
#   1. voice_input_func displays a prompt asking for voice input
#   2. User presses and holds 'c' to speak
#   3. Speech is transcribed by faster-whisper
#   4. Transcribed text is sent to this UserProxy agent
#   5. Agent processes the input and continues execution
MistyEmotionSpeakingAgent_UserProxy = UserProxyAgent(
    name="UserProxy",
    description="Voice-enabled user proxy for interactive task execution.",
    input_func=voice_input_func,  # Voice input for seamless interaction
)

mistyemotionspeaking_inner_stop = TextMentionTermination("APPROVE")
mistyemotionspeaking_inner_team = RoundRobinGroupChat([MistyEmotionSpeakingAgent, MistyEmotionSpeakingAgent_UserProxy],
                                 termination_condition=mistyemotionspeaking_inner_stop,max_turns=100)

MistyEmotionSpeakingAgent_SOM = SocietyOfMindAgent(
    name="MistyEmotionSpeakingAgent_SOM",
    team=mistyemotionspeaking_inner_team,
    description="Execute all Misty commands solvable by speech; any speech-executable command must be handled by this agent.",
    instruction="Output exactly: TERMINATE",  
)



# async def main():
#     print("=== MistyEmotionSpeakingAgent_SOM 已启动 ===")
#     print("提示：输入自然语言任务（如：'Cheerfully say good morning and wave.'）。输入 APPROVE 退出。\n")

#     # 用 Console 渲染 RoundRobinGroupChat 的消息流
#     await Console(MistyEmotionSpeakingAgent_SOM.run_stream(task="Say Shanana Hi Hi"))

# if __name__ == "__main__":
#     asyncio.run(main())