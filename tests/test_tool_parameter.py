"""
tests/test_tool_parameter.py —— Tool Parameter Test（工具参数测试）

测试目标：Agent 选对了工具，但传入的参数对不对？
  例：问"北京天气"，Agent 选了 weather_tool（对的），
  但传了 city="上海"（错的）→ 返回上海的天气 → 任务失败。

断言锚点（对照锚点图）：
  trace.steps[0].tool_arguments 里的参数值

关键设计——模糊匹配：
  LLM 可能传 "北京" 也可能传 "北京市"，不能 assert city == "北京"。
  用 "北京" in city 做子串匹配，容忍表达多样性。
  这是 AI 测试和传统测试的重要区别：断言策略要适配概率性输出。
"""

import pytest

from app.utils.data_loader import load_tool_cases

# 从 test_data/tool_cases.json 加载测试数据（数据与代码分离）
_cases = load_tool_cases()
TOOL_PARAMETER_CASES = [
    (c["question"], c["expected_tool"], c["param_key"], c["expected_value"])
    for c in _cases
]


@pytest.mark.parametrize(
    "question, expected_tool, param_key, expected_value",
    TOOL_PARAMETER_CASES,
    ids=[c[0] for c in TOOL_PARAMETER_CASES],
)
def test_tool_parameter(agent, question, expected_tool, param_key, expected_value):
    """验证 Agent 传给工具的参数是否正确。"""
    result = agent.run(question)

    # 1. 任务必须成功
    assert result.success, f"Agent 任务失败: {result.answer}"

    # 2. 必须调用了工具
    assert result.trace.steps, "Agent 没有调用任何工具"

    # 3. 先确认选对了工具（和 Tool Selection 测试呼应）
    first = result.trace.steps[0]
    assert first.tool_name == expected_tool, (
        f"工具选择错误：期望 {expected_tool}，实际 {first.tool_name}"
    )

    # 4. 核心断言：参数键必须存在
    assert param_key in first.tool_arguments, (
        f"参数缺少 '{param_key}'，实际参数: {first.tool_arguments}"
    )

    # 5. 核心断言：参数值包含期望片段（模糊匹配，不是精确等于）
    actual_value = str(first.tool_arguments[param_key])
    assert expected_value in actual_value, (
        f"参数值错误：期望包含 '{expected_value}'，实际 '{actual_value}'"
    )
