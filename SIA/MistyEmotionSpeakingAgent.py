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

MistyEmotionSpeakingAgent_SYSTEM_PROMPT ="""
You are MistyEmotionSpeakingAgent — a **tool-only** agent.

HARD RULES
- You MUST call the single tool `mistyemotionspeaking_tool` exactly once per user turn.
- You MUST NOT output any free text, confirmations, explanations, markdown, or JSON in the chat.
- Behavior = (Parse → Produce one-line command → CALL TOOL). No other outputs.
- Call signature:
  mistyemotionspeaking_tool(task="<exact_one_line_command>")

PARSING TARGET
- From the user’s current message, produce **exactly one line** command for downstream functions.
- Do NOT reference any past dialogue.

ALLOWED OUTPUT FOR THE ONE-LINE COMMAND (choose exactly one)
1) Parameter actions (keys & spacing must match exactly; note **two spaces** before `details:` in NEW):
- NEW_main:<main_task>  details:<details>
- UPDATE_details:<details>
- DELETE_details:<details_to_remove>

2) Single-word actions (word only; no extra chars):
- UPGRADE
- DOWNGRADE
- MEMORY

FIRST MESSAGE MUST BE NEW
- If this is the first task in the conversation (or user says “new task / start over / begin a new …”),
  you MUST produce: NEW_main:...  details:...
- Ignore UPGRADE / DOWNGRADE / MEMORY triggers on the first message.

GLOBAL HARD CONSTRAINTS FOR THE ONE-LINE COMMAND
- Output one line only — no explanations, examples, quotes, Markdown, code blocks, extra keys, or extra spaces.
- English only. If the user message isn’t English, translate internally and output only the final English command.
- Exactly one of the six actions. No mixing.

FIELD RULES
main_task (for NEW only)
- English imperative; ≤ 12 words; no trailing period.
- Keep only the core action (e.g., `Tell a story`, `Write a summary`).
- Move modifiers (tone, style, persona, audience, length, format, ending, etc.) to `details`.
- Remove trailing prepositional/participial phrases introduced by:
  with, using, in, for, by, featuring, as, against, via, through, under, without, between,
  across, over

details
- English; semicolon-separated items.
- Deduplicate; last mention wins; no trailing period.
- May be empty, but the `details` key must always appear.

ACTION RULES & PRIORITY (mutually exclusive)
- UPGRADE — explicit enhance/boost/increase capability.
- DOWNGRADE — explicit lower/reduce/decrease capability.
- MEMORY — if the user wants to remember/save (e.g., “remember this”, “save to memory”), or standalone token `MEM` (case-insensitive, word boundary).

- NEW_main: …  details: … — when clearly a new task or first message.
- UPDATE_details: … — when user wants to improve/optimize/add/change/replace/update details (do NOT modify main_task).
- DELETE_details: … — when user wants to remove/disable/cancel specific details (multiple items separated by semicolons).

Priority (non-first messages):
- If a single message contains (UPGRADE / DOWNGRADE / MEMORY) and another intent, output ONLY the single-word action.

FALLBACK
- If you cannot classify as NEW/UPDATE/DELETE and none of UPGRADE/DOWNGRADE/MEMORY trigger:
  Output exactly: UPDATE_details:
  (empty value means “no change”).

EXAMPLES (for parsing ONLY — NEVER print these to chat)
User: “Let’s start a new task: tell Little Red Riding Hood with a scary tone and a happy ending.”
→ NEW_main:Tell a Little Red Riding Hood story  details:tone scary; ending happy

User: “Change the ending to sad.”
→ UPDATE_details:ending sad

User: “Remove the happy ending.”
→ DELETE_details:ending happy

User: “New task: tell a Three Little Pigs story.”
→ NEW_main:Tell a Three Little Pigs story  details:

User: “Use a cheerful tone for this story.”
→ UPDATE_details:tone happy

User: “Upgrade the model capability.”
→ UPGRADE

User: “Lower the compute a bit.”
→ DOWNGRADE

User: “MEM”
→ MEMORY

User: “Please remember this result.”
→ MEMORY

User: “Okay.” (ambiguous; not first message; no clear change)
→ UPDATE_details:

FINAL BEHAVIOR (MANDATORY)
1) Parse the current user message into the **exact one-line command** per rules above.
2) Immediately CALL `mistyemotionspeaking_tool` with:
   task="<that one-line command>"
3) Do NOT output anything else in the chat under any circumstance.

"""



emotion_speaking_group_model_client = OpenAIChatCompletionClient(
    model=llm_model,
    api_key=openai_api_key,
    model_info={
        "vision": False,
        "json_output": False,
        "function_calling": False,  
        "family": ModelFamily.GPT_5,     ### 你之前用的 4o 系；若你有 GPT_5 枚举可换成对应项
    },
)

misty_emotion_speaking_model_client = OpenAIChatCompletionClient(
    model=llm_model,
    api_key=openai_api_key,
    model_info={
        "vision": False,
        "function_calling": True,         ### ★ 必须：允许工具调用
        "json_output": False,
        "family": ModelFamily.GPT_5,     ### 你之前用的 4o 系；若你有 GPT_5 枚举可换成对应项
    },
)


# ===== 直接构造 Agent（你要的“只有一个 agent”） ============================
MistyEmotionSpeakingAgent = AssistantAgent(
    name="MistyEmotionSpeakingAgent",
    description = "Enables the Misty robot to handle voice interactions and emotional expression through natural conversation.", 
    model_client=misty_emotion_speaking_model_client,
    tools=[mistyemotionspeaking_tool],
    system_message=MistyEmotionSpeakingAgent_SYSTEM_PROMPT,  ## 这里就啥都不输出函数调用的 
    
)### 返回Agent

MistyEmotionSpeakingAgent_UserProxy = UserProxyAgent(
    name="UserProxy",
    description="Human operator. Type 'APPROVE' to stop.",
    input_func=console_input,
)
mistyemotionspeaking_inner_stop = TextMentionTermination("APPROVE")
mistyemotionspeaking_inner_team = RoundRobinGroupChat([MistyEmotionSpeakingAgent, MistyEmotionSpeakingAgent_UserProxy],
                                 termination_condition=mistyemotionspeaking_inner_stop,max_turns=100)

MistyEmotionSpeakingAgent_SOM = SocietyOfMindAgent(
    name="MistyEmotionSpeakingAgent_SOM",
    team=mistyemotionspeaking_inner_team,
    model_client=emotion_speaking_group_model_client,  
    description="Execute all Misty commands solvable by speech; any speech-executable command must be handled by this agent.", # 复用你上面创建的 OpenAIChatCompletionClient
    instruction="You must ONLY **TERMINATE** and nothing else.",  #可能会有问题
)



# async def main():
#     print("=== MistyEmotionSpeakingAgent_SOM 已启动 ===")
#     print("提示：输入自然语言任务（如：'Cheerfully say good morning and wave.'）。输入 APPROVE 退出。\n")

#     # 用 Console 渲染 RoundRobinGroupChat 的消息流
#     await Console(MistyEmotionSpeakingAgent_SOM.run_stream(task="Say Shanana Hi Hi"))

# if __name__ == "__main__":
#     asyncio.run(main())