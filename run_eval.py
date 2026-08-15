"""
运行 Agent 评测，输出真实指标数据。

用法：python run_eval.py

这个脚本做两件事：
  1. 运行 10 个评测用例，计算量化指标 + 性能指标
  2. 对前 3 个用例做 LLM-as-a-Judge 语义评分（省 token）

所有数字来自真实运行，直接可以写进简历。
"""

from app.agent.agent import Agent
from app.evaluator.metrics import run_evaluation, EVAL_CASES
from app.evaluator.llm_judge import LLMJudge


def main():
    agent = Agent(role="employee")

    print("=" * 60)
    print("  Agent 评测开始（10 个用例，真实调用 LLM）")
    print("  预计耗时 1-2 分钟...")
    print("=" * 60)

    # ---- 第 1 部分：量化指标 + 性能指标 ----
    report = run_evaluation(agent)
    report.print_summary()

    # ---- 第 2 部分：LLM-as-a-Judge 语义评分 ----
    print("\n" + "=" * 60)
    print("  LLM-as-a-Judge 语义评分（前 3 个用例）")
    print("=" * 60)

    judge = LLMJudge()
    for cr in report.case_results[:3]:
        case = cr.case
        agent_result = cr.agent_result

        # 从 Trace 里拿工具返回的数据
        tool_result = {}
        if agent_result.trace.steps:
            tool_result = agent_result.trace.steps[0].tool_result

        # 构造期望描述
        expected_desc = f"应该调用 {case.expected_tool}，回答包含: {', '.join(case.expected_keywords)}"

        print(f"\n  {case.id}: {case.input}")
        result = judge.judge(
            question=case.input,
            expected=expected_desc,
            answer=agent_result.answer,
            tool_result=tool_result,
        )
        print(f"    score={result.score:.2f}  passed={result.passed}")
        print(f"    reason: {result.reason}")

    # ---- 保存报告到 JSON ----
    import json
    report_path = "reports/eval_report.json"
    import os
    os.makedirs("reports", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存到 {report_path}")


if __name__ == "__main__":
    main()
