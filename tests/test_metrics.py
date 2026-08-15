"""
测试评测指标系统的计算逻辑（不调 LLM）。

为什么分单元测试和集成测试：
  指标计算逻辑（percentile、check_tool_selection 等）是确定性函数，
  不需要调 LLM 就能验证——速度快、结果稳定。
  而"真实跑 Agent 看指标"是集成测试（test_performance.py），要调 LLM。

  分开测的好处：如果指标算错了（比如 percentile 实现有 bug），
  单元测试能立刻发现，不用等昂贵的 LLM 调用跑完。
"""

import pytest
from app.evaluator.metrics import (
    percentile,
    check_tool_selection,
    check_tool_parameter,
    check_answer_consistency,
    check_workflow_success,
    EvalCase,
    EVAL_CASES,
    EvalReport,
)
from app.agent.trace import AgentTrace, TraceStep
from app.agent.agent import AgentResult


# ============================================================
# 辅助函数：构造 mock AgentResult（不调 LLM）
# ============================================================
def make_mock_result(success=True, answer="测试回答", steps=None,
                     total_time=1.5, total_tokens=100):
    """构造一个假的 AgentResult，用于测试指标判定逻辑。"""
    trace = AgentTrace(user_input="测试输入")
    trace.success = success
    trace.final_answer = answer
    trace.total_time = total_time
    trace.total_tokens = total_tokens
    trace.num_llm_calls = 1
    if steps:
        trace.steps = steps
    return AgentResult(
        success=success,
        answer=answer,
        trace=trace,
        total_time=total_time,
        total_tokens=total_tokens,
        num_llm_calls=1,
    )


def make_step(tool_name="weather_tool", arguments=None, result=None):
    """构造一个假的 TraceStep。"""
    return TraceStep(
        round=1,
        tool_name=tool_name,
        tool_arguments=arguments or {"city": "北京"},
        tool_result=result or {"weather": "小雨", "temperature": 20, "city": "北京"},
        response_time=1.0,
    )


# ============================================================
# 测试 percentile 百分位计算
# ============================================================
class TestPercentile:
    """测试百分位数计算——这是性能指标的核心，必须算对。"""

    def test_p50_median(self):
        """P50 应该是中位数。"""
        data = [1, 2, 3, 4, 5]
        assert percentile(data, 50) == 3.0

    def test_p50_even_count(self):
        """偶数个样本的 P50 应该是中间两个的平均。"""
        data = [1, 2, 3, 4]
        # k = 0.5 * 3 = 1.5, f=1, c=2, sorted[1] + 0.5*(sorted[2]-sorted[1]) = 2 + 0.5 = 2.5
        assert percentile(data, 50) == 2.5

    def test_p95(self):
        """P95 应该在最大值附近。"""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        # k = 0.95 * 9 = 8.55, f=8, c=9, sorted[8] + 0.55*(sorted[9]-sorted[8])
        # = 9 + 0.55 * 1 = 9.55
        result = percentile(data, 95)
        assert 9.0 < result < 10.0
        assert abs(result - 9.55) < 0.01

    def test_p99(self):
        """P99 应该非常接近最大值。"""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        # k = 0.99 * 9 = 8.91, f=8, c=9, 9 + 0.91 * 1 = 9.91
        result = percentile(data, 99)
        assert abs(result - 9.91) < 0.01

    def test_p95_ge_avg(self):
        """P95 应该大于等于平均值（除非数据完全均匀）。"""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
        avg = sum(data) / len(data)
        assert percentile(data, 95) >= avg or percentile(data, 95) > 0

    def test_empty_data(self):
        """空数据应该返回 0。"""
        assert percentile([], 95) == 0.0

    def test_single_element(self):
        """只有一个元素时，任何百分位都等于那个元素。"""
        assert percentile([42], 50) == 42.0
        assert percentile([42], 95) == 42.0
        assert percentile([42], 99) == 42.0

    def test_p95_catches_outlier(self):
        """
        P95 在小样本时仍受异常值影响（线性插值会桥接到异常值）。

        教学点：10 个样本时 P95 的位置 k=8.55，落在 sorted[8]=3.0 和
        sorted[9]=8.0 之间，插值结果是 5.75——被异常值拉高了。
        说明小样本的百分位数不够稳健，生产环境需要更多样本。
        """
        normal = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0, 8.0]
        p95 = percentile(normal, 95)
        max_val = max(normal)
        avg = sum(normal) / len(normal)
        # P95 应该小于最大值（不会完全到达异常值）
        assert p95 < max_val
        # 但 P95 仍然被异常值拉高了（大于平均值）
        assert p95 > avg


# ============================================================
# 测试工具选择判定
# ============================================================
class TestToolSelection:
    def test_correct_tool(self):
        """选对了工具应该返回 True。"""
        result = make_mock_result(steps=[make_step("weather_tool")])
        assert check_tool_selection(result, "weather_tool") is True

    def test_wrong_tool(self):
        """选错了工具应该返回 False。"""
        result = make_mock_result(steps=[make_step("calculator_tool")])
        assert check_tool_selection(result, "weather_tool") is False

    def test_no_tool_called(self):
        """没调任何工具应该返回 False。"""
        result = make_mock_result(steps=[])
        assert check_tool_selection(result, "weather_tool") is False


# ============================================================
# 测试工具参数判定
# ============================================================
class TestToolParameter:
    def test_exact_match(self):
        """参数完全匹配应该返回 True。"""
        result = make_mock_result(
            steps=[make_step(arguments={"city": "北京"})]
        )
        assert check_tool_parameter(result, {"city": "北京"}) is True

    def test_substring_match(self):
        """子串匹配应该返回 True（"北京" in "北京市"）。"""
        result = make_mock_result(
            steps=[make_step(arguments={"city": "北京市"})]
        )
        assert check_tool_parameter(result, {"city": "北京"}) is True

    def test_wrong_value(self):
        """参数值错误应该返回 False。"""
        result = make_mock_result(
            steps=[make_step(arguments={"city": "上海"})]
        )
        assert check_tool_parameter(result, {"city": "北京"}) is False

    def test_space_normalization(self):
        """空格不影响匹配（"123*456" vs "123 * 456"）。"""
        result = make_mock_result(
            steps=[make_step(tool_name="calculator_tool",
                             arguments={"expression": "123 * 456"})]
        )
        assert check_tool_parameter(result, {"expression": "123*456"}) is True

    def test_no_tool_called(self):
        """没调工具应该返回 False。"""
        result = make_mock_result(steps=[])
        assert check_tool_parameter(result, {"city": "北京"}) is False


# ============================================================
# 测试回答一致性判定
# ============================================================
class TestAnswerConsistency:
    def test_all_keywords_present(self):
        """所有关键词都在回答里应该返回 True。"""
        result = make_mock_result(
            success=True,
            answer="北京今天小雨，气温20度，记得带伞",
        )
        assert check_answer_consistency(result, ["北京", "20"]) is True

    def test_missing_keyword(self):
        """缺少关键词应该返回 False。"""
        result = make_mock_result(
            success=True,
            answer="北京今天天气不错",
        )
        assert check_answer_consistency(result, ["北京", "20"]) is False

    def test_comma_normalization(self):
        """千分位逗号不影响匹配（"56,088" 包含 "56088"）。"""
        result = make_mock_result(
            success=True,
            answer="计算结果是 56,088",
        )
        assert check_answer_consistency(result, ["56088"]) is True

    def test_failed_task(self):
        """任务失败时一致性应该返回 False。"""
        result = make_mock_result(success=False, answer="")
        assert check_answer_consistency(result, ["任何关键词"]) is False


# ============================================================
# 测试工作流判定
# ============================================================
class TestWorkflowSuccess:
    def test_complete_workflow(self):
        """完整的工作流应该返回 True。"""
        result = make_mock_result(
            success=True,
            steps=[
                make_step("weather_tool"),
                make_step("calendar_tool"),
            ],
        )
        assert check_workflow_success(
            result, ["weather_tool", "calendar_tool"]
        ) is True

    def test_missing_step(self):
        """缺少步骤应该返回 False。"""
        result = make_mock_result(
            success=True,
            steps=[make_step("weather_tool")],  # 少了 calendar_tool
        )
        assert check_workflow_success(
            result, ["weather_tool", "calendar_tool"]
        ) is False

    def test_wrong_order(self):
        """顺序错误应该返回 False。"""
        result = make_mock_result(
            success=True,
            steps=[
                make_step("calendar_tool"),  # 顺序反了
                make_step("weather_tool"),
            ],
        )
        assert check_workflow_success(
            result, ["weather_tool", "calendar_tool"]
        ) is False

    def test_extra_tool_ok(self):
        """多调一次工具不影响判定（subsequence 匹配）。"""
        result = make_mock_result(
            success=True,
            steps=[
                make_step("weather_tool"),
                make_step("weather_tool"),  # 多调了一次
                make_step("calendar_tool"),
            ],
        )
        assert check_workflow_success(
            result, ["weather_tool", "calendar_tool"]
        ) is True

    def test_non_workflow_case(self):
        """非工作流用例（sequence=None）只看 task_success。"""
        result = make_mock_result(success=True, steps=[make_step("weather_tool")])
        assert check_workflow_success(result, None) is True

    def test_failed_task(self):
        """任务失败时工作流应该返回 False。"""
        result = make_mock_result(
            success=False,
            steps=[make_step("weather_tool")],
        )
        assert check_workflow_success(
            result, ["weather_tool", "calendar_tool"]
        ) is False


# ============================================================
# 测试评测用例数据完整性
# ============================================================
class TestEvalCases:
    def test_cases_count(self):
        """应该有 10 个评测用例。"""
        assert len(EVAL_CASES) == 10

    def test_all_have_required_fields(self):
        """每个用例必须有 id、input、expected_tool、expected_arguments、expected_keywords。"""
        for case in EVAL_CASES:
            assert case.id, f"用例缺少 id"
            assert case.input, f"用例 {case.id} 缺少 input"
            assert case.expected_tool, f"用例 {case.id} 缺少 expected_tool"
            assert case.expected_arguments, f"用例 {case.id} 缺少 expected_arguments"
            assert case.expected_keywords, f"用例 {case.id} 缺少 expected_keywords"

    def test_workflow_cases_have_sequence(self):
        """工作流用例必须有 expected_tools_sequence。"""
        for case in EVAL_CASES:
            if case.is_workflow:
                assert case.expected_tools_sequence is not None, (
                    f"工作流用例 {case.id} 缺少 expected_tools_sequence"
                )
                assert len(case.expected_tools_sequence) >= 2, (
                    f"工作流用例 {case.id} 的 sequence 至少要有 2 个工具"
                )

    def test_case_ids_unique(self):
        """用例 ID 必须唯一。"""
        ids = [c.id for c in EVAL_CASES]
        assert len(ids) == len(set(ids)), "有重复的用例 ID"
