# team_misty_selector.py
# 适配 AutoGen 0.5+（AgentChat API），只用 selector_prompt，不用 candidate_func
import asyncio                                                          ### 异步入口

from autogen_agentchat.teams import SelectorGroupChat                   ### 选择器团队
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination  ### 终止条件
from autogen_agentchat.ui import Console                                ### 可选：流式控制台输出
from autogen_ext.models.openai import OpenAIChatCompletionClient 
from PIA.MIsty_Process_State_Rehydrate import rehydrate_from_registry
from Misty_callback_summary import process_all_cb_files
from PIA.MistySensorAgent import MistySensorAgent_SOM                           ### 你的传感器 Agent（已配好）
from SIA.MistyEmotionSpeakingAgent import MistyEmotionSpeakingAgent_SOM     
import os#
import json## 你的情绪/说话 Agent（已配好）

def load_config(config_filename="config.json"):
    """
    加载当前目录的配置文件
    :param config_filename: 配置文件名 (默认 config.json)
    :return: 配置字典 config
    """
    # 获取当前文件所在目录
    current_dir = os.path.dirname(__file__)
    
    # 拼接到当前目录
    config_path = os.path.join(current_dir, config_filename)
    config_path = os.path.abspath(config_path)  # 转绝对路径
    
    # 读取 JSON 配置
    with open(config_path, "r") as f:
        config = json.load(f)
    
    return config

cfg = load_config("MistyPilot_config.json")  
OPENAI_API_KEY = cfg["openai_api_key"]

def reset_misty_state() -> None:
    """
    删除当前目录下的临时 JSON 文件：
    - misty_speaking_action_state.json
    - temp_emotion_speaking_mp3.json
    - thinking_model_power.json
    - cb_functions_summary.json
    """
    files_to_delete = [
        "misty_speaking_action_state.json",
        "temp_emotion_speaking_mp3.json",
        "thinking_model_power.json",
        "cb_functions_summary.json"
    ]

    for fname in files_to_delete:
        if os.path.exists(fname):                     ### 确认文件存在
            os.remove(fname)                          ### 删除文件
            print(f"Deleted: {fname}")                ### 输出反馈
        else:
            print(f"File not found: {fname}")                ### 输出反馈

async def misty_pilot(task:str) -> None:
    reset_misty_state()
    rehydrate_from_registry("misty_proc_registry.json", mode="replace")
    process_all_cb_files() 
    model_client = OpenAIChatCompletionClient(model="gpt-5-nano-2025-08-07",api_key=OPENAI_API_KEY)      ### 仅用于“选谁说话”
  
    termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(20)  ### 出现口令或到达上限

    selector_prompt = """Select the next agent to speak.

                    {roles}

                    Conversation:
                    {history}

                    Participants: {participants}

                    Routing rules:
                    - If the task can be solved **ONLY** through language (telling a story, dialogue, saying a sentence, greeting, or emotion-related) you must choose MistyEmotionSpeakingAgent_SOM
                    If the task explicitly mentions or implicitly implies any **physical interaction with Misty** (e.g., touch, bump, press, sensors, feet, head), or if it requires registering/handling sensor events, you must choose MistySensorAgent_SOM.
                    Return ONLY one name from {participants}.
                    """


    team = SelectorGroupChat(
        participants=[MistySensorAgent_SOM, MistyEmotionSpeakingAgent_SOM],
        model_client=model_client,
        termination_condition=termination,
        selector_prompt=selector_prompt,
        allow_repeated_speaker=False,
    )

    await Console(team.run_stream(task=task))    
    ### 如不需要流式：result = await team.run(task=task)


if __name__ == "__main__":
    # asyncio.run(misty_pilot(task="Main task: A friend has a headache and needs comfort.Detail: Anxious, ask why this is happening, ask if they need my help, and ask if they need to contact a doctor."))
    asyncio.run(misty_pilot(task="我摸你的头 你表现的很开心"))
    # asyncio.run(misty_pilot(task="删除所有传感器上注册的动作"))
    # asyncio.run(misty_pilot(task="给我讲习近平大战川普的故事"))
    # asyncio.run(misty_pilot(task="我摸你的左前方bumper 你表现的很惊讶"))
  



