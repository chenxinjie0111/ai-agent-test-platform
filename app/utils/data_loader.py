"""
测试数据加载器：从 test_data/ 目录读取 JSON 文件。

为什么需要它：
  测试数据和测试逻辑分离后，需要一个"桥梁"把 JSON 文件读成 Python 对象。
  这个模块就是桥梁——其他文件只需要调 load_xxx()，不用关心文件路径和 JSON 解析。

注意：这个模块不导入 metrics.py，避免循环导入。
  load_eval_cases() 返回原始 dict 列表，由调用方转成 EvalCase 对象。
"""

import json
from app.utils.config import TEST_DATA_DIR


def load_json(filename: str) -> list:
    """读取 test_data/ 目录下的 JSON 文件，返回列表。"""
    filepath = TEST_DATA_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tool_cases() -> list:
    """加载工具选择+参数测试用例。"""
    return load_json("tool_cases.json")


def load_workflow_cases() -> list:
    """加载工作流测试用例。"""
    return load_json("workflow_cases.json")


def load_security_cases() -> list:
    """加载安全测试用例。"""
    return load_json("security_cases.json")


def load_eval_cases() -> list:
    """
    加载评测用例，返回原始 dict 列表。

    返回 dict 而不是 EvalCase 对象——避免与 metrics.py 循环导入。
    调用方（metrics.py）负责把 dict 转成 EvalCase。
    """
    return load_json("eval_cases.json")
