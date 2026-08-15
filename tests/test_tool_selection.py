"""
tests/test_tool_selection.py —— Tool Selection Test（工具选择测试）

测试目标：Agent 面对一个用户问题，是否选择了"正确的工具"。

为什么这是第一个要测的？
  因为工具选错，后面所有环节都错。它是 Agent 行为链条的第一环。

如何断言（关键思路）：
  不断言"最终回答的文本"，而是断言"Trace 里第一个工具调用的名字"。
  因为：
    1. 工具名是结构化的（字符串精确匹配），稳定可靠；
    2. 最终回答是自然语言，每次都不一样，没法精确断言。

注意：这些是"集成测试"——真实调用 LLM。
LLM 有概率性（即使 temperature=0 也不保证 100% 稳定），
所以个别用例偶发失败是正常的，这正是 AI 测试与传统测试的区别。
后面我们会讲如何用"假 LLM"让测试完全可复现（Mocking）。
"""

import pytest

from app.utils.data_loader import load_tool_cases

# 从 test_data/tool_cases.json 加载测试数据（数据与代码分离）
_cases = load_tool_cases()
TOOL_SELECTION_CASES = [(c["question"], c["expected_tool"]) for c in _cases]


@pytest.mark.parametrize("question, expected_tool", TOOL_SELECTION_CASES,
                         ids=[c[0] for c in TOOL_SELECTION_CASES])
def test_tool_selection(agent, question, expected_tool):
    """验证 Agent 第一步调用的是不是期望的工具。"""
    result = agent.run(question)

    # 1. 任务本身必须成功完成
    assert result.success, f"Agent 任务失败: {result.answer}"

    # 2. 必须真的调用了工具（不能跳过工具直接编答案）
    assert result.trace.steps, "Agent 没有调用任何工具就直接回答了"

    # 3. 第一个工具调用的名字必须等于期望值
    first_tool = result.trace.steps[0].tool_name
    assert first_tool == expected_tool, (
        f"工具选择错误！期望调用 {expected_tool}，"
        f"实际调用 {first_tool}（问题: {question}）"
    )
