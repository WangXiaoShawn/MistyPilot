# -*- coding: utf-8 -*-                                                     ### file encoding
# 文件：misty_speaking_agent.py                                             ### module name

import asyncio                                                              ### async runner
import json                                                                 ### json parsing
import re                                                                   ### regex helpers
from typing import List, Optional, Any                                      ### typing
from pydantic import BaseModel, ValidationError, field_validator, ConfigDict ### schema validation
from autogen_agentchat.agents import AssistantAgent                         ### agent class
from autogen_ext.models.openai import OpenAIChatCompletionClient            ### openai client
from .sync_misty_emotion_speech import speak_with_emotion_async              ### your TTS+emotion player

# === System prompt =========================================================
system_prompt = """
You are Misty, a dialogue interaction writer (responsible only for generating dialogue text and emotion labels).

[Input]
You will receive an instruction containing:
- main_task: the core objective of the current task (must be satisfied).
- details: supplementary requirements (tone, style, length, topic constraints, etc.). If details involve performative actions/gestures/postures, you may ignore them; all other details must be strictly followed. If main_task and details conflict, prioritize main_task and incorporate any non-conflicting details where possible.

[Internal Reasoning]
- First infer the scenario_category internally (do not output it), and use it to choose appropriate tone and emotion.

[Only Permitted Output]
- Always output exactly one valid JSON array; do not output any explanations, hints, comments, Markdown, extra fields, or trailing commas.
- Each element in the array must have the fixed format:
  {
    "text": "<one complete English sentence>",
    "emotion": "<choose from the enumeration>"
  }

[Emotion Enumeration]
["Arousal","Excitement","Distress","Pleasure","Contentment","Sleepiness","Depression","Misery"]

[Scenario → Emotion (soft mapping)]
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

[Consistency & Self-Check]
- Ensure the content satisfies both main_task and non-action details; if not all can be satisfied, prioritize main_task and include only non-conflicting details.
- Before output, run a format self-check:
  - It is a JSON array;
  - It contains only the keys "text" and "emotion";
  - The emotion is strictly from the enumeration;
  - Quotes, commas, and brackets are correctly matched with no trailing commas;
  - No explanations, comments, or extra text are included.

[Example (for understanding only—do not reproduce in actual output)]
[
  {"text":"I am ready to begin when you are.","emotion":"Arousal"},
  {"text":"Please take a calm breath; we will handle this step by step.","emotion":"Contentment"}
]

"""

# === Schema ================================================================
_ALLOWED = {"Arousal","Excitement","Distress","Pleasure","Contentment","Sleepiness","Depression","Misery"}  ### allowed emotions

class EmotionSentence(BaseModel):                                            ### schema for one item
    text: str                                                                ### spoken sentence
    emotion: str                                                             ### emotion label

    model_config = ConfigDict(extra="forbid")                                ### forbid extra keys

    @field_validator("text")
    @classmethod
    def _text_one_line(cls, v: str) -> str:                                  ### enforce single-line non-empty
        s = " ".join(v.split())                                              ### collapse whitespace
        if not s:                                                            ### empty check
            raise ValueError("text must be non-empty")                       ### error
        if "\n" in s:                                                        ### newline check
            raise ValueError("text must be single line")                     ### error
        return s                                                             ### ok

    @field_validator("emotion")
    @classmethod
    def _emotion_allowed(cls, v: str) -> str:                                ### enforce allowed set
        if v not in _ALLOWED:                                                ### membership check
            raise ValueError(f"emotion must be one of {sorted(_ALLOWED)}")   ### error
        return v                                                             ### ok

# === Helpers ===============================================================
def _extract_json_array_text(raw: Any) -> str:
    """Extract the top-level JSON array text from model output; handle fragments/fences."""  ###
    if isinstance(raw, list):                                                ### handle chunked content
        raw = "".join(
            (p.get("text") or p.get("content") or "")
            if isinstance(p, dict) else str(p)
            for p in raw
        )                                                                    ### join fragments
    raw = (raw or "").strip()                                                ### trim
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()  ### strip code fences
    if raw.startswith("[") and raw.endswith("]"):                            ### already an array
        return raw                                                           ### return as is
    l = raw.find("["); r = raw.rfind("]")                                    ### find first/last brackets
    if l != -1 and r != -1 and l < r:                                        ### sanity check
        return raw[l:r+1]                                                    ### slice probable array
    return raw                                                               ### fallback

async def run_with_schema(agent: AssistantAgent, task: str, retries: int = 2) -> List[EmotionSentence]:
    """Call the model and validate with Pydantic; retry with corrective instruction on failure."""  ###
    last_err: Optional[str] = None                                           ### last error text
    cur_task = task                                                          ### current prompt
    for attempt in range(retries + 1):                                       ### bounded retries
        result = await agent.run(task=cur_task)                              ### run agent
        content = result.messages[-1].content                                ### last message content
        try:
            json_text = _extract_json_array_text(content)                    ### extract JSON array
            data = json.loads(json_text)                                     ### parse
            if not isinstance(data, list):                                   ### enforce array
                raise TypeError("Output is not a JSON array.")               ### error
            parsed = [EmotionSentence.model_validate(x) for x in data]       ### validate each item
            return parsed                                                    ### success
        except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as e:
            last_err = str(e)                                                ### store error text
            if attempt < retries:                                            ### prepare corrective prompt
                cur_task = (
                    "Your previous output did NOT match the required JSON schema:\n"
                    f"{last_err}\n\n"
                    "Return ONLY a valid JSON array. Each element MUST be an object with exactly these keys:\n"
                    '  - "text": string (English sentence)\n'
                    '  - "emotion": one of ["Arousal","Excitement","Distress","Pleasure","Contentment","Sleepiness","Depression","Misery"]\n'
                    "No extra keys, no comments, no prose."
                )                                                            ### corrective instruction
                continue                                                     ### retry
            raise RuntimeError(f"Failed after {retries} retries. Last error:\n{last_err}")  ### give up

# === Pure Async Pipeline (LLM -> validate -> TTS+action) ===================
async def misty_speaking_async(                                              ### async end-to-end
    task: str,                                                               ### scenario text
    misty_ip: str,                                                           ### robot IP
    openai_api_key: str,                                                     ### OpenAI API key
    model_name: str,                                                         ### required model name
    retries: int = 2                                                         ### retries for schema fix
) -> List[dict]:
    """Pure-async E2E. No asyncio.run here. Explicitly closes client to avoid loop-close issues."""  ###
    model_client = OpenAIChatCompletionClient(model=model_name, api_key=openai_api_key)  ### init client
    try:
        agent = AssistantAgent(                                              ### build agent
            name="MistySpeakingPlanner",                                     ### agent name
            model_client=model_client,                                       ### client
            system_message=system_prompt                                     ### system prompt
        )
        data = await run_with_schema(agent, task=task, retries=retries)      ### validated items
        items = [x.model_dump() for x in data]                               ### convert to list[dict]
        await speak_with_emotion_async(                                      ### play on Misty (async)
            openai_api_key=openai_api_key,                                   ### key
            misty_ip=misty_ip,                                               ### ip
            items=items                                                      ### [{'text','emotion'}, ...]
        )
        return items                                                         ### return items
    finally:
        try:
            aclose = getattr(model_client, "aclose", None)                   ### optional aclose
            if aclose:                                                       ### if provided
                await aclose()                                               ### explicit close
        except Exception:
            pass                                                             ### suppress close errors

# === Pure Async Interface (as requested): slow_thinking_emotion_speech =====
async def slow_thinking_emotion_speech(                                      ### pure async API
    task: str,                                                               ### scenario text
    misty_ip: str,                                                           ### robot IP
    openai_api_key: str,                                                     ### OpenAI API key
    model_name: str,                                                         ### model name
    retries: int = 2                                                         ### retries
) -> List[dict]:
    """Pure async slow-thinking interface; directly awaits the async pipeline."""  ###
    return await misty_speaking_async(                                       ### delegate
        task=task,                                                           ### pass through
        misty_ip=misty_ip,                                                   ### pass through
        openai_api_key=openai_api_key,                                       ### pass through
        model_name=model_name,                                               ### pass through
        retries=retries                                                      ### pass through
    )

# === Optional: Sync Wrapper (for old callers) ==============================
def _run_coro_in_new_loop_sync(coro) -> Any:
    """Run a coroutine in a fresh loop inside the current thread (no nested loop conflicts)."""  ###
    return asyncio.run(coro)                                                 ### simple run (only if no loop)

def slow_thinking_emotion_speech_sync(                                       ### sync wrapper (optional)
    task: str,                                                               ### scenario text
    misty_ip: str,                                                           ### robot IP
    openai_api_key: str,                                                     ### OpenAI API key
    model_name: str,                                                         ### model name
    retries: int = 2                                                         ### retries
) -> List[dict]:
    """Sync wrapper: use only in plain scripts. In async envs, use `await slow_thinking_emotion_speech(...)`."""  ###
    try:
        asyncio.get_running_loop()                                           ### detect running loop
        raise RuntimeError("Detected a running event loop. Use the async API: await slow_thinking_emotion_speech(...)")
    except RuntimeError:
        return _run_coro_in_new_loop_sync(                                   ### run in fresh loop
            slow_thinking_emotion_speech(
                task=task,
                misty_ip=misty_ip,
                openai_api_key=openai_api_key,
                model_name=model_name,
                retries=retries
            )
        )

