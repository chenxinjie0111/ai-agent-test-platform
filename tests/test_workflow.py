"""
tests/test_workflow.py —— Multi-step Workflow Test（多步骤工作流测试）

测试目标：多步骤 Agent 任务的步骤完整性、顺序、参数、条件逻辑。

这是阶段三最复杂的测试，也是最接近真实业务的。
多步任务"查天气 → 判断下雨 → 创建提醒"可能出的问题：
  - 漏步骤：只查了天气，忘了创建提醒（阶段二踩的 bug 就是这种）
  - 顺序错：先创建提醒再查天气（逻辑荒谬）
  - 参数错：提醒标题写成"开会"而不是"带伞"
  - 条件逻辑错：明明下雨却没创建提醒

断言锚点（对照锚点图）：
  steps 列表的整体（顺序 + 完整性）+ 各 step 的参数

设计决策——为什么用一个测试函数 + 多个断言：
  这是集成测试，每次 agent.run() 要调 3 轮 LLM。
  拆成 5 个独立测试 = 15 轮 LLM 调用，太慢太烧 token。
  合并到一个函数里，一次调用验证所有维度，是合理的工程权衡。
  （单元测试追求"一测一事"，集成测试追求"一次调用多维验证"。）
"""

import pytest

# 多步任务的标准测试问题
WORKFLOW_QUESTION = (
    '北京今天天气怎么样？如果下雨，帮我创建明天早上8点的"记得带伞"提醒'
)


def test_workflow_complete(agent):
    """
    多步任务综合验证：一次调用，检查 6 个维度。

    这正是阶段二踩过的 bug 的"测试版"：
      当时 LLM 没时钟 → 只调 weather 不调 calendar → 漏步骤。
      如果当时有这个测试，就会自动报"缺少 calendar_tool 步骤"。
    """
    result = agent.run(WORKFLOW_QUESTION)

    # ---- 维度1：任务必须成功 ----
    assert result.success, f"Agent 任务失败: {result.answer}"

    # ---- 维度2：步骤完整 ----
    # 提取所有工具名，检查 weather_tool 和 calendar_tool 都在
    tool_names = [s.tool_name for s in result.trace.steps]
    assert "weather_tool" in tool_names, (
        f"缺少 weather_tool 步骤，实际调用的工具: {tool_names}"
    )
    assert "calendar_tool" in tool_names, (
        f"缺少 calendar_tool 步骤（可能漏了创建提醒），实际: {tool_names}"
    )

    # ---- 维度3：顺序正确 ----
    # weather 必须在 calendar 之前（先查天气，才能判断是否下雨）
    weather_idx = tool_names.index("weather_tool")
    calendar_idx = tool_names.index("calendar_tool")
    assert weather_idx < calendar_idx, (
        f"工具调用顺序错误：weather 应在 calendar 之前，"
        f"实际顺序: {tool_names}"
    )

    # ---- 维度4：条件逻辑 ----
    # 北京的模拟天气是"小雨"，所以应该触发"创建带伞提醒"
    weather_step = result.trace.steps[weather_idx]
    weather = weather_step.tool_result.get("weather")
    assert weather == "小雨", (
        f"北京模拟天气应为'小雨'，实际: {weather_step.tool_result}"
    )
    # 既然下雨，calendar_tool 就应该被调用（上面维度2已验证）
    # 这里再加一条：如果天气不是小雨，就不应该调 calendar（反向验证）
    # 但我们的模拟数据北京固定是小雨，所以正向验证即可

    # ---- 维度5：参数正确 ----
    # calendar_tool 的 title 应该包含"伞"（因为下雨才需要伞）
    calendar_step = result.trace.steps[calendar_idx]
    title = calendar_step.tool_arguments.get("title", "")
    assert "伞" in title, (
        f"提醒标题应包含'伞'（因为下雨），实际: '{title}'"
    )

    # ---- 维度6：最终回答 ----
    # 回答应该提到提醒已创建
    answer = result.answer
    assert any(w in answer for w in ["提醒", "已创建", "已设置", "创建", "设置"]), (
        f"回答应提到提醒已创建: {answer}"
    )
