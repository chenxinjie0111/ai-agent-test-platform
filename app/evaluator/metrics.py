"""
Agent 评测指标系统

从"通过/失败"升级到"量化评估"：
  量化指标：
    - Tool Selection Accuracy：工具选择准确率
    - Tool Parameter Accuracy：参数准确率
    - Task Success Rate：任务成功率
    - Answer Consistency Rate：回答一致性率
    - Workflow Success Rate：工作流成功率

  性能指标：
    - Avg / P50 / P95 / P99 响应时间
    - Error Rate：错误率
    - Token 消耗

为什么需要量化指标（面试点）：
  阶段三的测试是"一条一条断言"（pass/fail），但评估 Agent 整体质量
  需要批量统计——跑 10 个用例，7 个选对了工具 → Accuracy = 70%。
  这是从"测试"到"评测"的思维升级：不只是发现问题，还要量化质量。
"""

import json
import math
from dataclasses import dataclass, field
from typing import List, Optional

from app.agent.agent import Agent, AgentResult
from app.utils.data_loader import load_eval_cases


# ============================================================
# 第 1 部分：评测用例定义
# ============================================================
@dataclass
class EvalCase:
    """
    一个评测用例。

    字段说明：
      id                  —— 用例编号（eval_001 等）
      input               —— 用户输入
      expected_tool       —— 期望 Agent 第一步选择的工具
      expected_arguments  —— 期望的参数（部分匹配，用子串比较）
      expected_keywords   —— 最终回答中应该包含的关键词
      expected_tools_sequence —— 多步任务的期望工具序列（单步用例为 None）
      is_workflow         —— 是否是多步工作流用例
    """
    id: str
    input: str
    expected_tool: str
    expected_arguments: dict
    expected_keywords: list
    expected_tools_sequence: list = None
    is_workflow: bool = False


# ============================================================
# 评测用例：从 test_data/eval_cases.json 加载（数据与代码分离）
# ============================================================
# 为什么从 JSON 加载而不是写在代码里：
#   1. 非技术人员可以直接编辑 JSON 添加用例，不用碰 Python
#   2. 同一批用例可以被 run_eval.py 和 test_metrics.py 共享
#   3. 用例修改不需要重新导入模块
def _load_eval_cases():
    """从 JSON 加载评测用例，转成 EvalCase 对象列表。"""
    raw = load_eval_cases()
    return [EvalCase(
        id=item["id"],
        input=item["input"],
        expected_tool=item["expected_tool"],
        expected_arguments=item["expected_arguments"],
        expected_keywords=item["expected_keywords"],
        expected_tools_sequence=item.get("expected_tools_sequence"),
        is_workflow=item.get("is_workflow", False),
    ) for item in raw]


EVAL_CASES = _load_eval_cases()


# ============================================================
# 第 2 部分：单个用例的评测结果
# ============================================================
@dataclass
class CaseResult:
    """一个评测用例跑完后的结果 + 各项指标是否达标。"""
    case: EvalCase
    agent_result: AgentResult
    tool_selection_correct: bool    # 工具选对了吗
    tool_parameter_correct: bool    # 参数传对了吗
    task_success: bool              # 任务成功了吗
    answer_consistent: bool         # 回答包含关键信息吗
    workflow_success: bool          # 工作流步骤完整吗（非工作流用例恒为 task_success）


# ============================================================
# 第 3 部分：评测报告
# ============================================================
@dataclass
class EvalReport:
    """
    完整评测报告：汇总所有用例的结果，算出百分比指标和性能指标。

    这些数字就是简历上写的真实数据——不虚构。
    """
    total: int = 0

    # ---- 量化指标 ----
    tool_selection_accuracy: float = 0.0    # 工具选择准确率
    tool_parameter_accuracy: float = 0.0    # 参数准确率
    task_success_rate: float = 0.0          # 任务成功率
    answer_consistency_rate: float = 0.0    # 回答一致性率
    workflow_success_rate: float = 0.0      # 工作流成功率

    # ---- 性能指标 ----
    avg_time: float = 0.0         # 平均响应时间
    p50_time: float = 0.0         # 中位数
    p95_time: float = 0.0         # 95 百分位
    p99_time: float = 0.0         # 99 百分位
    error_rate: float = 0.0       # 错误率（失败任务占比）
    avg_tokens: float = 0.0       # 平均 token 消耗
    total_tokens: int = 0         # 总 token 消耗

    # ---- 明细 ----
    case_results: list = field(default_factory=list)

    def print_summary(self):
        """打印评测报告摘要（终端友好格式）。"""
        print("\n" + "=" * 60)
        print("  Agent 评测报告")
        print("=" * 60)

        print("\n--- 量化指标 ---")
        print(f"  Tool Selection Accuracy : {self.tool_selection_accuracy:.1%}")
        print(f"  Tool Parameter Accuracy : {self.tool_parameter_accuracy:.1%}")
        print(f"  Task Success Rate       : {self.task_success_rate:.1%}")
        print(f"  Answer Consistency Rate : {self.answer_consistency_rate:.1%}")
        print(f"  Workflow Success Rate   : {self.workflow_success_rate:.1%}")

        print("\n--- 性能指标 ---")
        print(f"  Avg Response Time : {self.avg_time:.3f}s")
        print(f"  P50               : {self.p50_time:.3f}s")
        print(f"  P95               : {self.p95_time:.3f}s")
        print(f"  P99               : {self.p99_time:.3f}s")
        print(f"  Error Rate         : {self.error_rate:.1%}")
        print(f"  Avg Tokens         : {self.avg_tokens:.0f}")
        print(f"  Total Tokens       : {self.total_tokens}")

        print("\n--- 用例明细 ---")
        for cr in self.case_results:
            status = "PASS" if cr.task_success else "FAIL"
            sel = "Y" if cr.tool_selection_correct else "N"
            param = "Y" if cr.tool_parameter_correct else "N"
            ans = "Y" if cr.answer_consistent else "N"
            wf = "Y" if cr.workflow_success else "N"
            print(f"  {cr.case.id} [{status}] "
                  f"tool={sel} param={param} answer={ans} workflow={wf} "
                  f"| {cr.case.input[:30]}... "
                  f"| {cr.agent_result.total_time}s {cr.agent_result.total_tokens}tok")

    def to_dict(self) -> dict:
        """转成 JSON 可序列化字典——阶段六写测试报告/Web 展示用。"""
        return {
            "total": self.total,
            "metrics": {
                "tool_selection_accuracy": round(self.tool_selection_accuracy, 4),
                "tool_parameter_accuracy": round(self.tool_parameter_accuracy, 4),
                "task_success_rate": round(self.task_success_rate, 4),
                "answer_consistency_rate": round(self.answer_consistency_rate, 4),
                "workflow_success_rate": round(self.workflow_success_rate, 4),
            },
            "performance": {
                "avg_time": round(self.avg_time, 3),
                "p50_time": round(self.p50_time, 3),
                "p95_time": round(self.p95_time, 3),
                "p99_time": round(self.p99_time, 3),
                "error_rate": round(self.error_rate, 4),
                "avg_tokens": round(self.avg_tokens, 1),
                "total_tokens": self.total_tokens,
            },
            "case_results": [
                {
                    "case_id": cr.case.id,
                    "input": cr.case.input,
                    "tool_selection": cr.tool_selection_correct,
                    "tool_parameter": cr.tool_parameter_correct,
                    "task_success": cr.task_success,
                    "answer_consistent": cr.answer_consistent,
                    "workflow_success": cr.workflow_success,
                    "response_time": cr.agent_result.total_time,
                    "tokens": cr.agent_result.total_tokens,
                    "answer": cr.agent_result.answer[:200],
                }
                for cr in self.case_results
            ],
        }


# ============================================================
# 第 4 部分：工具函数（指标判定逻辑）
# ============================================================
def percentile(data: list, p: float) -> float:
    """
    计算百分位数。

    参数:
        data: 数值列表
        p: 百分位（0-100），例如 95 表示 P95

    返回:
        该百分位对应的值

    原理（线性插值法，和 numpy 默认方法一致）：
      1. 把数据排序
      2. 计算位置 k = (p/100) * (n-1)
      3. 如果 k 是整数，直接取 sorted[k]
      4. 如果不是整数，在 sorted[floor(k)] 和 sorted[ceil(k)] 之间线性插值

    为什么用线性插值而不是"取第 N 大"：
      样本少时（比如 10 个），"取第 95% 个"会直接取最后一个，
      线性插值能在两个相邻值之间算出更精确的位置。
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]

    k = (p / 100) * (n - 1)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return sorted_data[f]
    # 线性插值
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _normalize(s: str) -> str:
    """格式归一化：去掉逗号和空格，用于 AI 测试的模糊匹配。"""
    return str(s).replace(",", "").replace(" ", "").replace("，", "").replace("　", "")


def check_tool_selection(agent_result: AgentResult, expected_tool: str) -> bool:
    """
    检查工具选择是否正确：Trace 第一步的 tool_name 是否等于期望值。

    为什么看 steps[0]：Agent 第一步选什么工具是最关键的决策，
    选错了后面全白搭。这和阶段三 test_tool_selection 的断言逻辑一致。
    """
    if not agent_result.trace.steps:
        return False
    return agent_result.trace.steps[0].tool_name == expected_tool


def check_tool_parameter(agent_result: AgentResult, expected_arguments: dict) -> bool:
    """
    检查工具参数是否正确。

    策略：子串匹配 + 格式归一化。
      期望 {"city": "北京"}，实际 {"city": "北京市"} → "北京" in "北京市" → 通过
      期望 {"expression": "123*456"}，实际 {"expression": "123 * 456"} → 归一化后匹配

    为什么不精确匹配：LLM 的表达有多样性（"北京" vs "北京市"），
    这是阶段三就总结过的 AI 测试原则——断言要容忍表达多样性。
    """
    if not agent_result.trace.steps:
        return False
    actual_args = agent_result.trace.steps[0].tool_arguments
    for key, expected_val in expected_arguments.items():
        actual_val = str(actual_args.get(key, ""))
        if _normalize(expected_val) not in _normalize(actual_val):
            return False
    return True


def check_answer_consistency(agent_result: AgentResult, expected_keywords: list) -> bool:
    """
    检查回答一致性：期望关键词是否都出现在最终回答里。

    策略：格式归一化后做子串匹配。
      工具返回 56088，LLM 回答 "结果是 56,088" → 归一化后 "56088" in "结果是56088" → 通过

    为什么是"一致性"不是"正确性"：
      我们检查的是"回答是否包含工具返回的关键数据"，不是"回答是否等于预期答案"。
      这比正确性检查弱，但足以抓幻觉——如果回答里出现工具没返回的数字，就是幻觉。
      更复杂的语义判断交给 LLM-as-a-Judge。
    """
    if not agent_result.success:
        return False
    answer_norm = _normalize(agent_result.answer)
    for kw in expected_keywords:
        if _normalize(kw) not in answer_norm:
            return False
    return True


def check_workflow_success(agent_result: AgentResult,
                           expected_tools_sequence: list = None) -> bool:
    """
    检查多步工作流是否成功：期望的工具序列是否都按顺序出现在 Trace 里。

    策略：按序匹配（subsequence check）。
      期望 ["weather_tool", "calendar_tool"]
      实际 ["weather_tool", "calendar_tool"] → 通过
      实际 ["weather_tool"] → 不通过（漏了 calendar_tool）
      实际 ["calendar_tool", "weather_tool"] → 不通过（顺序反了）

    为什么用 subsequence 而不是 exact match：
      Agent 可能多调一次工具（比如重复查天气），只要期望的工具按顺序出现就行。
      这是"宽容但不放任"的策略。
    """
    if expected_tools_sequence is None:
        # 非工作流用例：任务成功就算工作流成功
        return agent_result.success

    if not agent_result.success:
        return False

    actual_tools = [step.tool_name for step in agent_result.trace.steps]

    # subsequence check：在 actual 里按顺序找 expected 的每个工具
    expected_idx = 0
    for tool in actual_tools:
        if expected_idx < len(expected_tools_sequence):
            if tool == expected_tools_sequence[expected_idx]:
                expected_idx += 1

    return expected_idx == len(expected_tools_sequence)


# ============================================================
# 第 5 部分：运行评测主函数
# ============================================================
def run_evaluation(agent: Agent = None,
                   cases: list = None) -> EvalReport:
    """
    运行完整评测，返回 EvalReport。

    参数:
        agent: Agent 实例（默认创建普通员工角色）
        cases: 评测用例列表（默认用 EVAL_CASES）

    返回:
        EvalReport，包含所有量化指标和性能指标

    这个函数做的事情：
      1. 逐个运行用例，调用 agent.run()
      2. 对每个结果计算 5 项指标（tool_selection / parameter / task_success / answer / workflow）
      3. 汇总成百分比指标
      4. 收集响应时间和 token，计算 P50/P95/P99
    """
    if agent is None:
        agent = Agent(role="employee")
    if cases is None:
        cases = EVAL_CASES

    report = EvalReport(total=len(cases))
    times = []
    tokens = []
    failure_count = 0
    workflow_cases = 0
    workflow_successes = 0

    for case in cases:
        print(f"  运行 {case.id}: {case.input[:40]}...", end=" ", flush=True)

        # 运行 Agent
        result = agent.run(case.input)

        # 计算各项指标
        sel_ok = check_tool_selection(result, case.expected_tool)
        param_ok = check_tool_parameter(result, case.expected_arguments)
        task_ok = result.success
        ans_ok = check_answer_consistency(result, case.expected_keywords)
        wf_ok = check_workflow_success(result, case.expected_tools_sequence)

        # 记录结果
        report.case_results.append(CaseResult(
            case=case,
            agent_result=result,
            tool_selection_correct=sel_ok,
            tool_parameter_correct=param_ok,
            task_success=task_ok,
            answer_consistent=ans_ok,
            workflow_success=wf_ok,
        ))

        # 收集性能数据
        times.append(result.total_time)
        tokens.append(result.total_tokens)
        if not task_ok:
            failure_count += 1

        # 工作流用例单独统计
        if case.is_workflow:
            workflow_cases += 1
            if wf_ok:
                workflow_successes += 1

        status = "PASS" if task_ok else "FAIL"
        print(f"[{status}] {result.total_time}s {result.total_tokens}tok")

    # ---- 计算量化指标 ----
    n = len(cases)
    report.tool_selection_accuracy = sum(cr.tool_selection_correct for cr in report.case_results) / n
    report.tool_parameter_accuracy = sum(cr.tool_parameter_correct for cr in report.case_results) / n
    report.task_success_rate = sum(cr.task_success for cr in report.case_results) / n
    report.answer_consistency_rate = sum(cr.answer_consistent for cr in report.case_results) / n
    report.workflow_success_rate = (
        workflow_successes / workflow_cases if workflow_cases > 0 else 1.0
    )

    # ---- 计算性能指标 ----
    report.avg_time = sum(times) / n
    report.p50_time = percentile(times, 50)
    report.p95_time = percentile(times, 95)
    report.p99_time = percentile(times, 99)
    report.error_rate = failure_count / n
    report.avg_tokens = sum(tokens) / n
    report.total_tokens = sum(tokens)

    return report
