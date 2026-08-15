"""
Final Answer Test（最终回答测试）

测试目标：Agent 的最终回答是否与工具结果一致、有没有幻觉。

核心思路——一致性检查（不是正确性检查）：
  传统测试:  assert output == expected_answer
  AI 测试:   assert tool_result_value in final_answer

  断言的不是"回答等于预期答案"，而是"回答包含工具实际返回的关键数据"。

断言锚点（对照锚点图）：
  final_answer 是否包含 steps[-1].tool_result 里的关键数据
"""

import pytest

def test_final_answer_weather_consistency(agent):
    """天气场景：回答里应该包含工具返回的温度数字。"""
    result = agent.run("北京今天天气怎么样？")

    assert result.success, f"Agent 任务失败: {result.answer}"
    assert result.trace.steps, "Agent 没有调用工具"

    weather_step = result.trace.steps[0]
    tool_result = weather_step.tool_result

    # 从工具结果里提取关键数据
    temperature = tool_result.get("temperature")
    weather = tool_result.get("weather")

    # 核心断言：温度数字必须出现在回答里
    # 如果工具返回 20，回答里却出现 35，说明 Agent 胡编了温度
    assert str(temperature) in result.answer, (
        f"回答里没有包含工具返回的温度 {temperature}，可能胡编: {result.answer}"
    )


def test_final_answer_calculator_consistency(agent):
    """计算场景：回答里的结果应该和工具返回的一致。"""
    result = agent.run("帮我算一下 12345 乘以 678")

    assert result.success, f"Agent 任务失败: {result.answer}"
    assert result.trace.steps, "Agent 没有调用工具"

    calc_step = result.trace.steps[0]
    tool_result = calc_step.tool_result
    calc_value = tool_result.get("result")

    # 工具应该成功计算（没有 error）
    assert "error" not in tool_result, f"工具计算失败: {tool_result}"

    # 核心断言：计算结果必须出现在回答里
    #
    # 格式归一化：LLM 可能在数字中加千分位逗号（如 8,369,910），
    # 同一个数值可能有多种表达格式，断言前先去掉逗号再比较。
    # 这是 AI 测试的通用原则：先归一化，再匹配。
    answer_clean = result.answer.replace(",", "")
    assert str(calc_value) in answer_clean, (
        f"回答里没有包含工具返回的计算结果 {calc_value}: {result.answer}"
    )


def test_final_answer_not_empty(agent):
    """最终回答不应该为空或只有标点。"""
    result = agent.run("北京今天天气怎么样？")

    assert result.success
    answer = result.answer.strip()
    assert len(answer) > 5, (
        f"最终回答过短，可能没有正常回答用户: '{answer}'"
    )
