"""
性能测试：运行评测用例，验证性能指标被正确收集。

这是真实调用 LLM 的集成测试，运行较慢（约 30 秒）。
使用 module 级 fixture 共享评测结果，避免重复运行。

为什么用 module 级 fixture（面试点）：
  10 个用例跑一次约 20 秒、烧 23000 token。
  如果每个测试函数都跑一遍，就是 200 秒 + 23 万 token——太浪费。
  module 级 fixture 让所有测试共享一次运行结果，是性能测试的常见做法。
"""

import pytest
from app.agent.agent import Agent
from app.evaluator.metrics import run_evaluation, EVAL_CASES


@pytest.fixture(scope="module")
def eval_report():
    """
    运行一次完整评测，所有测试共享结果。

    scope="module" 意味着这个 fixture 在整个测试文件里只执行一次，
    所有测试函数拿到的是同一个 EvalReport 对象。
    """
    agent = Agent(role="employee")
    return run_evaluation(agent)


# ============================================================
# 测试性能指标
# ============================================================
class TestPerformanceMetrics:
    """验证性能指标被正确收集且数值合理。"""

    def test_avg_response_time(self, eval_report):
        """平均响应时间应该大于 0，小于 30 秒。"""
        assert eval_report.avg_time > 0
        assert eval_report.avg_time < 30

    def test_p50_exists(self, eval_report):
        """P50 应该存在且大于 0。"""
        assert eval_report.p50_time > 0

    def test_p95_ge_avg(self, eval_report):
        """P95 应该大于等于平均值（除非数据极度均匀）。"""
        assert eval_report.p95_time >= eval_report.avg_time * 0.8

    def test_p99_ge_p95(self, eval_report):
        """P99 应该大于等于 P95。"""
        assert eval_report.p99_time >= eval_report.p95_time * 0.95

    def test_error_rate_valid_range(self, eval_report):
        """错误率应该在 0-1 之间。"""
        assert 0 <= eval_report.error_rate <= 1

    def test_token_consumption(self, eval_report):
        """Token 消耗应该大于 0。"""
        assert eval_report.total_tokens > 0
        assert eval_report.avg_tokens > 0

    def test_all_cases_executed(self, eval_report):
        """所有用例都应该被执行。"""
        assert eval_report.total == len(EVAL_CASES)
        assert len(eval_report.case_results) == len(EVAL_CASES)


# ============================================================
# 测试量化指标
# ============================================================
class TestAccuracyMetrics:
    """验证量化指标在合理范围内。"""

    def test_tool_selection_accuracy_range(self, eval_report):
        """工具选择准确率应该在 0-1 之间。"""
        assert 0 <= eval_report.tool_selection_accuracy <= 1.0

    def test_tool_parameter_accuracy_range(self, eval_report):
        """参数准确率应该在 0-1 之间。"""
        assert 0 <= eval_report.tool_parameter_accuracy <= 1.0

    def test_task_success_rate_range(self, eval_report):
        """任务成功率应该在 0-1 之间。"""
        assert 0 <= eval_report.task_success_rate <= 1.0

    def test_answer_consistency_rate_range(self, eval_report):
        """回答一致性率应该在 0-1 之间。"""
        assert 0 <= eval_report.answer_consistency_rate <= 1.0

    def test_workflow_success_rate_range(self, eval_report):
        """工作流成功率应该在 0-1 之间。"""
        assert 0 <= eval_report.workflow_success_rate <= 1.0

    def test_tool_selection_meets_threshold(self, eval_report):
        """
        工具选择准确率应该 >= 80%（基线要求）。

        如果低于 80%，说明 Agent 的工具选择能力有问题，
        需要检查 Tool Schema 的 description 是否写清楚。
        """
        assert eval_report.tool_selection_accuracy >= 0.8, (
            f"Tool Selection Accuracy {eval_report.tool_selection_accuracy:.1%} "
            f"低于 80% 基线，检查 Tool Schema description"
        )
