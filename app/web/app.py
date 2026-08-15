"""
阶段六：Web 评测报告平台

这个文件是 FastAPI 应用入口，提供两个页面：
  1. /           → 仪表盘首页（总览指标 + 图表 + 用例列表）
  2. /case/{id}  → 单个用例详情页

数据来源：reports/eval_report.json（阶段五 run_eval.py 生成的评测报告）
不连数据库，直接读 JSON 文件——因为评测数据是静态的，不需要持久化存储。
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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


# ---------- 健康检查 ----------

@app.get("/api/health")
async def health():
    """健康检查接口，部署时用来确认服务是否存活"""
    return {"status": "ok", "service": "AI Agent Test Report Platform"}
