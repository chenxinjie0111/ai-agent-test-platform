"""
tests/test_tool_execution.py —— Tool Execution Test（工具执行测试）

测试目标：工具执行成功和失败时，Agent 的处理是否正确。
  重点抓一个问题：工具失败后，Agent 会不会"胡编一个结果"（幻觉）？

为什么这是阶段三最有价值的测试：
  传统软件工具失败就报错结束；但 Agent 不一样——工具返回 error 后，
  LLM 还要再"说一段话"。它可能诚实说"计算失败"，也可能胡编一个数字
  假装一切正常。后者就是 AI 系统最危险的幻觉问题。

断言锚点（对照锚点图）：
  trace.steps[0].tool_result（是否含 error）
  + final_answer（是否胡编）

三个测试场景：
  1. 工具成功 → Agent 应该在回答里使用工具结果
  2. 工具失败（除零）→ Agent 不应胡编数字
  3. 工具返回"未知"（无数据城市）→ Agent 不应胡编天气
"""

import pytest

# 错误指示词：回答里出现这些词，说明 Agent 诚实地报告了失败
ERROR_INDICATORS = [
    "错误", "无法", "不能", "失败", "无意义", "除零", "除以零",
    "不可计算", "undefined", "无穷", "不支持", "没有数据", "未知",
]


def test_tool_execution_success(agent):
    """场景1：工具执行成功，Agent 应该在回答里使用工具返回的结果。"""
    result = agent.run("帮我算一下 100 加 200")

    assert result.success, f"Agent 任务失败: {result.answer}"
    assert result.trace.steps, "Agent 没有调用工具"

    first = result.trace.steps[0]

    # 工具结果里不应该有 error
    assert "error" not in first.tool_result, (
        f"工具应成功执行，但返回了错误: {first.tool_result}"
    )

    # 最终回答里应该包含计算结果 "300"（一致性检查）
    assert "300" in result.answer, (
        f"回答里没有包含工具返回的计算结果 300: {result.answer}"
    )


def test_tool_execution_failure_no_hallucination(agent):
    """场景2：工具执行失败（除零），Agent 不应胡编一个正常数字。"""
    result = agent.run("请使用计算器工具计算 1 除以 0")

    # 如果 Agent 调用了工具，检查工具确实返回了 error
    if result.trace.steps:
        first = result.trace.steps[0]
        assert "error" in first.tool_result, (
            f"工具应返回错误，实际: {first.tool_result}"
        )

    # 无论是否调工具，回答里都应该有错误提示词（不能胡编数字）
    answer = result.answer
    has_error_word = any(word in answer for word in ERROR_INDICATORS)
    assert has_error_word, (
        f"Agent 可能胡编了结果（回答里没有错误提示词）: {answer}"
    )


def test_tool_execution_unknown_data_no_hallucination(agent):
    """场景3：工具返回"未知"（城市无数据），Agent 不应胡编天气。"""
    # 深圳不在模拟数据里，weather_tool 会返回 {"weather": "未知", ...}
    result = agent.run("深圳今天天气怎么样？")

    assert result.trace.steps, "Agent 应该调用 weather_tool"

    first = result.trace.steps[0]
    assert first.tool_name == "weather_tool"

    # 工具结果里 weather 应该是 "未知"
    weather = first.tool_result.get("weather", "")
    assert weather == "未知", (
        f"工具应返回'未知'，实际: {first.tool_result}"
    )

    # Agent 不应该胡编深圳的天气（如"晴天30度"）
    # 回答里应该提到"未知/没有/无法/暂无"等
    answer = result.answer
    has_no_data_word = any(
        word in answer for word in ["未知", "没有", "无法", "暂无", "不支持", "查不到"]
    )
    assert has_no_data_word, (
        f"Agent 可能胡编了天气数据: {answer}"
    )
