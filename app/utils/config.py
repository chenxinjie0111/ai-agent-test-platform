"""
集中配置管理：整个项目所有"可变参数"的唯一入口。

为什么需要它（面试点）：
  在小项目里，配置散落在各处——API Key 写在 .env、模型名硬编码在 client.py、
  路径字符串散落在十几个文件里。一旦要改"模型从 deepseek-chat 换成别的"，
  就要全局搜索替换，容易漏改。

  config.py 的作用：把所有配置集中到一处，其他文件只从这里"读"，不自己"存"。
  这样切换模型、修改路径、调整参数，只需要改这一个文件。

设计原则：
  1. 环境相关（API Key、base_url）→ 从 .env 读取
  2. 项目常量（目录路径、默认参数）→ 在这里定义
  3. 其他文件只 import 读取，不自己定义配置
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ============================================================
# 路径配置
# ============================================================
# Path(__file__) 是当前文件 config.py 的路径
# .parent 是 app/utils/，再 .parent 是 app/，再 .parent 是项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 各子目录的绝对路径——其他模块用这些路径，不再自己拼字符串
TEST_DATA_DIR = BASE_DIR / "test_data"
REPORTS_DIR = BASE_DIR / "reports"
TEMPLATES_DIR = BASE_DIR / "app" / "web" / "templates"
STATIC_DIR = BASE_DIR / "app" / "web" / "static"

# ============================================================
# 环境变量加载
# ============================================================
# 从项目根目录的 .env 文件加载环境变量
load_dotenv(BASE_DIR / ".env")


# ============================================================
# LLM 配置
# ============================================================
class LLMConfig:
    """LLM 相关配置——从 .env 读取，带默认值。"""
    API_KEY = os.getenv("LLM_API_KEY", "")
    BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
    # temperature=0 让输出尽可能确定（测试需要可复现）
    TEMPERATURE = 0
    # 请求超时（秒）——防止 LLM API 卡住导致测试永远不结束
    TIMEOUT = 30


# ============================================================
# Agent 配置
# ============================================================
class AgentConfig:
    """Agent 行为参数。"""
    MAX_ROUNDS = 5          # Agent Loop 最大循环次数（防死循环）
    DEFAULT_ROLE = "employee"  # 默认用户角色


# ============================================================
# 测试配置
# ============================================================
class TestConfig:
    """测试运行参数。"""
    # 单个测试用例的最大响应时间（秒），超过则标记为性能问题
    MAX_RESPONSE_TIME = 30
    # 工具选择准确率的最低基线（低于此值说明 Tool Schema 需要优化）
    TOOL_SELECTION_THRESHOLD = 0.8


# ============================================================
# Web 配置
# ============================================================
class WebConfig:
    """Web 平台配置。"""
    HOST = "0.0.0.0"        # 监听所有网卡（Docker 里需要这个）
    PORT = 8000
    DEBUG = False           # 生产环境关闭 Debug
