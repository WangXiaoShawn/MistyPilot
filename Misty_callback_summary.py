# -*- coding: utf-8 -*-
import os
import ast
import json
from typing import Optional, Dict
def find_cb_function(file_path: str) -> str:
  
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    abs_path = os.path.abspath(file_path)   ### 转换成绝对路径

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=file_path)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("cb"):
            return f"{abs_path}:{node.name}"

    raise ValueError(f"No function starting with 'cb' found in {file_path}")

def get_function_docstring(file_path: str, func_name: str) -> Optional[str]:
    
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=file_path)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return ast.get_docstring(node)  # 提取 docstring

    return None

def process_all_cb_files() -> Dict[str, Dict[str, Optional[str]]]:
    results = {}
    cb_dir = "Misty_Call_Back_Func"
    
    if not os.path.exists(cb_dir):
        print(f"Warning: {cb_dir} directory not found!")
        return results
    
    for fname in os.listdir(cb_dir):
        if fname.endswith("_cb.py"):   ### 只匹配 _cb.py
            file_path = os.path.join(cb_dir, fname)
            try:
                func_path = find_cb_function(file_path)
                abs_path, func_name = func_path.split(":")
                docstring = get_function_docstring(file_path, func_name)
                results[fname] = {
                    "cb_func": func_path,
                    "docs": docstring
                }
            except Exception as e:
                results[fname] = {
                    "error": str(e)
                }

    out_file = "cb_functions_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results

if __name__ == "__main__":
    output = process_all_cb_files()
    print(f"结果已保存到 cb_functions_summary.json，共处理 {len(output)} 个文件")
