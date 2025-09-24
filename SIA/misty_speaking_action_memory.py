# -*- coding: utf-8 -*-                                                             ### file encoding
# db_native_chroma.py                                                               ### filename
import hashlib                                                                       ### for stable id (hash)
from typing import List, Dict, Any, Optional, Union                                  ### typing
import chromadb                                                                      ### Chroma client
from chromadb.api.models.Collection import Collection                                ### type hint
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction               ### openai embed fn
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

cfg = load_config("MistyPilot_config.json")  
OPENAI_API_KEY = cfg["openai_api_key"]
EMBED_MODEL = cfg["collection"]
# embedding model name

def init_client(persist_dir: Optional[str] = "./misty_emotion_action_speaking_store"):
    client = chromadb.PersistentClient(path=persist_dir)                              ### persistent client
    return client                                                                     ### return client

def get_or_create_collection(
    client,
    name: str = "text-embedding-3-large",
    extra_metadata: Optional[Dict[str, Any]] = None
) -> Collection:
    embedder = OpenAIEmbeddingFunction(                                              ### create embedding fn
        api_key=OPENAI_API_KEY,                                                      ### pass api key
        model_name=EMBED_MODEL                                                       ### set embed model
    )
    meta = {"hnsw:space": "cosine"}                                                  ### cosine space for HNSW
    if extra_metadata:                                                               ### if extra meta provided
        meta.update(extra_metadata)                                                  ### merge metadata
    col = client.get_or_create_collection(                                           ### get or create collection
        name=name,                                                                   ### collection name
        embedding_function=embedder,                                                 ### bind embedding fn
        metadata=meta                                                                ### index metadata
    )
    return col                                                                       ### return collection

def _make_stable_ids_from_texts(texts: List[str]) -> List[str]:
    ids = []                                                                         ### init id list
    for t in texts:                                                                  ### iterate texts
        h = hashlib.sha1(t.encode("utf-8")).hexdigest()[:16]                         ### sha1 -> 16 hex
        ids.append(f"doc_{h}")                                                       ### prefix + hash
    return ids                                                                       ### return ids

def upsert_texts(
    col: Collection,
    texts: Union[str, List[str]],                                                    ### 支持 str 或 List[str]
    paths: Optional[Union[str, List[str]]] = None,                                   ### 路径（str 或 List[str]）
    ids: Optional[Union[str, List[str]]] = None                                      ### 可选自定义 id
):
    if isinstance(texts, str):                                                       ### 标准化为列表
        texts = [texts]                                                              ### wrap to list
    if isinstance(ids, str):                                                         ### 标准化 ids
        ids = [ids]                                                                  ### wrap to list
    if isinstance(paths, str):                                                       ### 标准化 paths
        paths = [paths]                                                              ### wrap to list

    if ids is None:                                                                  ### 如未提供 ids
        ids = _make_stable_ids_from_texts(texts)                                     ### 用内容哈希生成稳定 id

    if paths is None:                                                                ### 如未提供路径
        metadatas: List[Dict[str, Any]] = [{} for _ in texts]                        ### 填空元数据
    else:
        if len(paths) != len(texts):                                                 ### 长度校验
            raise ValueError(                                                        ### 报错：长度不一致
                f"Length mismatch: texts={len(texts)} paths={len(paths)}"
            )
        metadatas = [                                                                ### 组装目标元数据
            {"emotion_action_speaking_path": p} for p in paths                       ### 唯一字段：路径
        ]

    if not (len(texts) == len(metadatas) == len(ids)):                               ### 再次长度一致性校验
        raise ValueError(                                                            ### 抛出错误
            f"Length mismatch: texts={len(texts)} metadatas={len(metadatas)} ids={len(ids)}"
        )

    col.upsert(documents=texts, metadatas=metadatas, ids=ids)                        ### 执行 upsert

def query_emotion_action_speak_task(
    col: Collection,
    query: str,
    threshold: float = 0.2   ### 默认阈值，可外部传入
) -> Optional[str]:
    try:
        res = col.query(
            query_texts=[query],
            n_results=1,
            include=["metadatas", "distances"]
        )
    except Exception as e:
        print(f"[ERROR] query failed: {e}")
        return None

    # 如果没有结果，直接返回 None
    if not res.get("distances") or not res["distances"][0]:
        print("[INFO] no result found")
        return None

    # 取出 top1 的距离与元数据
    distance = res["distances"][0][0]
    meta = res["metadatas"][0][0] if res.get("metadatas") and res["metadatas"][0] else {}

    print(f"[DEBUG] distance = {distance:.4f}")   ### 打印相似度

    # 阈值过滤
    if distance > threshold:
        print(f"[INFO] distance {distance:.4f} > threshold {threshold}, returning None")
        return None

    return meta.get("emotion_action_speaking_path")

