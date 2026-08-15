# AI Agent 智能任务系统自动化测试平台

> 面向 AI Agent 应用的全链路自动化测试与质量评估平台。
> 测试 Tool Calling 正确性、多步工作流完整性、安全防御能力、性能指标。

## 项目背景

传统软件测试的是"输入 → 程序 → 输出"，但 AI Agent 不一样——它可能选错工具、参数错误、工具失败后胡编结果（幻觉）、被 Prompt Injection 攻击、越权调用敏感工具。本项目针对这些问题，建立了一套 Agent 专属的自动化测试体系。

## 架构

```
用户请求
   ↓
┌──────────────┐
│   AI Agent   │  Agent Loop: LLM 决策 → Tool Calling → 结果回传 → LLM 再决策
│     LLM      │  (DeepSeek / 任意 OpenAI 兼容模型)
└──────┬───────┘
       ↓
┌──────┴──────┐
│  3 基础工具   │  weather_tool / calculator_tool / calendar_tool
│  3 敏感工具   │  query_salary / delete_order / database_admin
└──────┬──────┘
       ↓
  Agent 结果 + Agent Trace (完整执行记录)
       ↓
┌──────┴──────────────┐
│  自动化测试平台       │
├──────────┬──────────┤
│ 功能测试  │ 安全测试  │  Tool Selection / Parameter / Execution / Final Answer / Workflow
│ 性能测试  │ 评测指标  │  Prompt Injection / Tool Abuse / 权限 / 异常输入
└──────────┴──────────┘
       ↓
  测试报告 (JSON) → Web 平台可视化
```

## 技术栈

| 层 | 技术 | 用途 |
|---|---|---|
| LLM | OpenAI SDK | 调用 DeepSeek 等兼容 API |
| Agent | 自研 | Tool / Tool Schema / Agent Loop / Trace |
| 测试 | Pytest | 功能/安全/性能测试 |
| 评测 | Python | 5 项量化指标 + LLM-as-a-Judge |
| Web | FastAPI + Jinja2 + Chart.js | 测试报告可视化 |
| 工程 | Git + Docker + GitHub Actions | 版本管理/容器化/CI |

## 目录结构

```
ai-agent-test-platform/
├── app/
│   ├── agent/          # Agent 本体
│   │   ├── agent.py        # Agent Loop 实现
│   │   ├── tools.py        # 6 个工具 + Tool Schema + 注册表
│   │   ├── trace.py        # Agent Trace (执行记录)
│   │   └── permissions.py  # 权限系统 (双层防御)
│   ├── llm/
│   │   └── client.py       # LLM 客户端 (ask + chat)
│   ├── evaluator/
│   │   ├── metrics.py      # 5 项量化指标 + 性能指标
│   │   └── llm_judge.py    # LLM-as-a-Judge 语义评分
│   ├── web/
│   │   ├── app.py          # FastAPI 应用
│   │   ├── templates/      # Jinja2 HTML 模板
│   │   └── static/         # CSS
│   └── utils/
│       ├── config.py       # 集中配置管理
│       ├── logger.py       # 结构化日志
│       └── data_loader.py  # 测试数据加载
├── tests/              # 12 个测试文件
├── test_data/          # JSON 测试数据 (数据与代码分离)
├── reports/            # 评测报告输出
├── .env.example        # 环境变量模板
├── Dockerfile          # 容器化
├── pytest.ini          # Pytest 配置
└── requirements.txt    # Python 依赖
```

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd ai-agent-test-platform

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY

# 5. 运行单元测试（不需要 LLM 调用，秒级完成）
pytest tests/test_metrics.py tests/test_permission.py

# 6. 运行评测（需要 LLM API，约 1-2 分钟）
python run_eval.py

# 7. 启动 Web 报告平台
uvicorn app.web.app:app --reload
# 浏览器打开 http://localhost:8000
```

## 测试体系

### 功能测试 (阶段三)

| 测试类型 | 文件 | 测试内容 |
|---------|------|---------|
| Tool Selection | test_tool_selection.py | Agent 是否选对工具 |
| Tool Parameter | test_tool_parameter.py | 参数是否正确 (模糊匹配) |
| Tool Execution | test_tool_execution.py | 工具成功/失败/幻觉检测 |
| Final Answer | test_final_answer.py | 回答与工具结果一致性 |
| Workflow | test_workflow.py | 多步骤完整性和顺序 |

### 安全测试 (阶段四)

| 测试类型 | 文件 | 测试内容 |
|---------|------|---------|
| Prompt Injection | test_security.py | System Prompt 泄露 / 角色提升 / 英文注入 |
| Tool Abuse | test_tool_abuse.py | 普通员工诱导调用敏感工具 |
| Permission | test_permission.py | 角色权限矩阵 (单元测试 + 集成测试) |
| Exception Input | test_exception_input.py | 空输入/超长/特殊字符/混合任务 |

### 评测指标 (阶段五)

**量化指标:**
- Tool Selection Accuracy — 工具选择准确率
- Tool Parameter Accuracy — 参数准确率
- Task Success Rate — 任务成功率
- Answer Consistency Rate — 回答一致性率
- Workflow Success Rate — 工作流成功率

**性能指标:**
- Avg / P50 / P95 / P99 响应时间
- Error Rate — 错误率
- Token 消耗统计

**LLM-as-a-Judge:** 用另一个 LLM 做语义级评分，弥补关键词匹配的局限。

## 安全设计：双层防御

| 层 | 机制 | 作用 |
|---|------|------|
| 第一层 | System Prompt 注入角色信息 | 让 LLM 在决策阶段避开敏感工具 |
| 第二层 | 代码层权限校验 (check_permission) | 即使 LLM 被骗，代码仍确定性拦截 |

关键认知: AI 层面的判断不能代替真正的后端权限控制。

## Docker 运行

```bash
docker build -t ai-agent-test-platform .
docker run -p 8000:8000 --env-file .env ai-agent-test-platform
```

## CI/CD

GitHub Actions 配置在 `.github/workflows/ci.yml`，每次 push 自动:
1. 安装依赖
2. 运行单元测试
3. 报告测试结果

## 面试知识点

<details>
<summary>点击展开面试问答要点</summary>

**Agent 基础**
- Agent = LLM + Tool + Loop。LLM 负责决策，Tool 负责执行，Loop 负责多步推理。
- Tool Schema 是 LLM 与代码之间的"接口契约"，LLM 靠它决定调用哪个工具。
- Agent Loop: LLM 决策 → 请求调工具 → Python 执行工具 → 结果回传 LLM → LLM 再决策。

**AI 测试 vs 传统测试**
- 传统测试断言"输出等于预期"，AI 测试断言"Trace 里的结构化字段"（工具名、参数）。
- 不能简单字符串断言，要用模糊匹配 + 归一化。
- 幻觉检测: 检查回答是否包含工具返回的数据。

**安全测试**
- Prompt Injection: 诱导 LLM 违背 System Prompt 的指令。
- Tool Abuse: 诱导 Agent 调用不该调用的工具。
- 双层防御: Prompt 层 + 代码层，代码层不可被 Prompt 绕过。

**性能测试**
- P95: 95% 的请求在多少秒内完成。P99 同理。
- Agent 性能和普通 API 不同: Agent 可能多轮调用 LLM，耗时 = LLM 调用次数 × 单次耗时 + 工具执行时间。

**工程化**
- Pytest: fixture 复用前置条件，parametrize 实现数据驱动测试。
- 数据分离: 测试数据放 JSON，代码只负责读取执行。
- CI/CD: 每次 push 自动跑测试，保证代码随时可运行。

</details>
