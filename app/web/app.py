"""
阶段六：Web 评测报告平台

这个文件是 FastAPI 应用入口，提供两个页面 + 三个 API：
  页面:
    1. /           → 仪表盘首页（总览指标 + 图表 + 用例列表）
    2. /case/{id}  → 单个用例详情页（含 Agent Trace 可视化）

  API:
    1. /api/health             → 健康检查
    2. /api/run-test/{case_id} → 运行单个测试用例，返回 trace + 指标
    3. /api/run-all            → 运行全部测试，保存报告并返回摘要

数据来源：reports/eval_report.json（run_eval.py 或 /api/run-all 生成）
不连数据库，直接读 JSON 文件——因为评测数据是静态的，不需要持久化存储。
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agent.agent import Agent
from app.evaluator.metrics import (
    EVAL_CASES,
    run_evaluation,
    check_tool_selection,
    check_tool_parameter,
    check_answer_consistency,
    check_workflow_success,
)

# ---------- 应用初始化 ----------

# Base directory: 项目根目录 (ai-agent-test-platform/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 创建 FastAPI 应用实例
app = FastAPI(title="AI Agent 测试报告平台")

# 挂载静态文件目录：/static/xxx → app/web/static/xxx
# 这样模板里可以用 /static/style.css 引用 CSS 文件
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)

# 初始化 Jinja2 模板引擎，指向 templates/ 目录
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ---------- 数据加载 ----------

def load_report() -> dict:
    """
    读取评测报告 JSON 文件。

    每次请求都重新读文件，这样重新跑 run_eval.py 后刷新页面就能看到最新数据，
    不需要重启服务器。
    """
    report_path = BASE_DIR / "reports" / "eval_report.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="评测报告不存在，请先运行: python run_eval.py",
        )
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- 路由 ----------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    仪表盘首页：
    - 展示 5 个准确率指标卡片
    - 展示性能指标卡片
    - 用 Chart.js 画响应时间分布图和指标雷达图
    - 列出所有评测用例（可点击查看详情）
    """
    report = load_report()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"report": report},
    )


@app.get("/case/{case_id}", response_class=HTMLResponse)
async def case_detail(request: Request, case_id: str):
    """
    单个用例详情页：
    - 展示用户输入、Agent 回答
    - 展示每项指标的通过/失败状态
    - 展示响应时间和 Token 消耗
    """
    report = load_report()
    # 在 case_results 列表中查找匹配的用例
    case = None
    for c in report.get("case_results", []):
        if c["case_id"] == case_id:
            case = c
            break

    if case is None:
        raise HTTPException(status_code=404, detail=f"用例 {case_id} 不存在")

    return templates.TemplateResponse(
        request,
        "case_detail.html",
        {"case": case},
    )


# ---------- 运行测试 API ----------

@app.post("/api/run-test/{case_id}")
def run_single_test(case_id: str):
    """
    运行单个评测用例，返回完整 trace + 指标结果。

    为什么用 def 而不是 async def：
      Agent.run() 内部会调用 LLM API，这是一个同步阻塞操作（等 HTTP 响应）。
      如果用 async def，会阻塞 FastAPI 的事件循环，导致其他请求排队等待。
      用 def，FastAPI 自动把它放到线程池执行，不会阻塞事件循环。

    返回格式和 eval_report.json 中 case_results 的结构一致，
    这样前端可以用同一套模板渲染。
    """
    # 1. 查找用例
    case = None
    for c in EVAL_CASES:
        if c.id == case_id:
            case = c
            break
    if case is None:
        raise HTTPException(status_code=404, detail=f"用例 {case_id} 不存在")

    # 2. 运行 Agent（可能因为 API Key 缺失等原因失败）
    try:
        agent = Agent(role="employee")
        result = agent.run(case.input)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent 运行失败，请检查 .env 中的 API Key 配置。错误: {str(e)}",
        )

    # 3. 计算指标（和 run_evaluation 里的逻辑一致）
    sel_ok = check_tool_selection(result, case.expected_tool)
    param_ok = check_tool_parameter(result, case.expected_arguments)
    task_ok = result.success
    ans_ok = check_answer_consistency(result, case.expected_keywords)
    wf_ok = check_workflow_success(result, case.expected_tools_sequence)

    # 4. 返回完整结果（含 trace）
    return {
        "case_id": case.id,
        "input": case.input,
        "expected_tool": case.expected_tool,
        "expected_arguments": case.expected_arguments,
        "expected_keywords": case.expected_keywords,
        "is_workflow": case.is_workflow,
        "tool_selection": sel_ok,
        "tool_parameter": param_ok,
        "task_success": task_ok,
        "answer_consistent": ans_ok,
        "workflow_success": wf_ok,
        "response_time": result.total_time,
        "tokens": result.total_tokens,
        "answer": result.answer,
        "trace": result.trace.to_dict(),
    }


@app.post("/api/run-all")
def run_all_tests():
    """
    运行全部评测用例，保存报告到 reports/eval_report.json，返回摘要。

    前端点击"运行全部测试"按钮时调用此 API。
    运行完成后刷新页面即可看到最新报告。
    """
    try:
        report = run_evaluation()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"评测运行失败，请检查 .env 中的 API Key 配置。错误: {str(e)}",
        )

    # 保存报告到 JSON
    reports_dir = BASE_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

    # 返回摘要
    passed = sum(1 for cr in report.case_results if cr.task_success)
    failed = report.total - passed
    return {
        "status": "ok",
        "total": report.total,
        "passed": passed,
        "failed": failed,
        "message": f"完成 {report.total} 个用例：{passed} 通过，{failed} 失败",
    }


# ---------- 健康检查 ----------

@app.get("/api/health")
async def health():
    """健康检查接口，部署时用来确认服务是否存活"""
    return {"status": "ok", "service": "AI Agent Test Report Platform"}
