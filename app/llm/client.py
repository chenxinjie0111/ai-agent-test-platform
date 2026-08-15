"""
LLM 客户端：整个测试平台与大模型交互的唯一入口。

用法:
    from app.llm.client import LLMClient
    client = LLMClient()
    result = client.ask("你好")
    if result.success:
        print(result.answer)
"""

import json
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIError,
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
)

# 找 .env：默认从当前运行目录找，找不到再回到项目根目录找
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


# ============================================================
# 第 1 部分：标准化返回结构
# ============================================================
@dataclass
class LLMResponse:
    """
    大模型调用的标准化返回结果。

    无论调用成功还是失败，ask() 都返回这个类型。
    这是"可测试性"的基础：断言面向字段，而不是面向一段文本。
    """
    success: bool                 # 调用是否成功
    question: str                 # 用户输入（原样保存，方便追溯）
    answer: str = ""              # 模型回答（失败时为空字符串）
    response_time: float = 0.0    # 响应时间（秒）—— 性能测试数据来源
    prompt_tokens: int = 0        # 输入消耗 token —— 成本统计来源
    completion_tokens: int = 0    # 输出消耗 token
    total_tokens: int = 0         # 总 token
    error: str = ""               # 错误描述（成功时为空）
    error_type: str = ""          # 错误类型名（成功时为空）


@dataclass
class ChatResponse:
    """
    Agent 专用的对话返回结构（阶段二新增）。

    与 LLMResponse 的区别：
      - LLMResponse: 面向"一问一答"，answer 就是最终文本
      - ChatResponse: 面向"Agent 循环"，LLM 可能不回答而是请求调用工具
    所以它同时携带 content（最终回答）和 tool_calls（工具调用请求）。

    tool_calls 是已经解析好的列表（arguments 已从字符串转成字典）：
        [{"id": "call_xxx", "name": "weather_tool", "arguments": {"city": "北京"}}]
    """
    success: bool
    content: str = ""                 # LLM 直接回答的文本（没调工具时才有）
    tool_calls: list = None           # 工具调用请求列表（没有则为 None）
    response_time: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str = ""

# ============================================================
# 第 2 部分：LLM 客户端类
# ============================================================
class LLMClient:
    """
    封装 LLM API 调用，提供统一、可测试的接口。
    """
    DEFAULT_SYSTEM_PROMPT = (
        "你是一个企业内部的智能办公助手，"
        "可以帮助员工查天气、做计算、管理日程提醒。"
    )

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")

        if not self.api_key:
            raise ValueError("缺少 LLM_API_KEY，请检查 .env 文件是否配置正确。")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def ask(self, question, system_prompt=None, temperature=0):
        """
        向大模型提问。
        """
        start_time = time.time()

        if system_prompt is None:
            system_prompt = self.DEFAULT_SYSTEM_PROMPT

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=temperature,
            )

            usage = response.usage

            return LLMResponse(
                success=True,
                question=question,
                answer=response.choices[0].message.content,
                response_time=round(time.time() - start_time, 3),
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

        except AuthenticationError:
            return self._fail(question, start_time,
                              "API Key 无效或已过期", "AuthenticationError")

        except RateLimitError:
            return self._fail(question, start_time,
                              "请求频率超限或账户余额不足", "RateLimitError")

        except APITimeoutError:
            return self._fail(question, start_time,
                              "请求超时，服务器未在规定时间内响应", "TimeoutError")

        except APIConnectionError:
            return self._fail(question, start_time,
                              "网络连接失败，请检查 base_url 或网络状态", "ConnectionError")

        except APIError as e:
            return self._fail(question, start_time,
                              f"API 返回错误: {e}", "APIError")

        except Exception as e:
            # 兜底：测试平台上跑成千上万次调用，绝不能因为一个
            # 未预料异常让整个测试任务崩溃
            return self._fail(question, start_time,
                              f"未知错误: {type(e).__name__}: {e}", "UnknownError")

    def chat(self, messages, tools=None, temperature=0):
        """
        Agent 专用对话方法（阶段二新增）。

        参数:
            messages: 完整对话历史列表，例如:
                [{"role": "system", "content": "..."},
                 {"role": "user", "content": "..."},
                 {"role": "tool", "content": "...", "tool_call_id": "call_xxx"}]
            tools: Tool Schema 列表（可选）。传了，LLM 才知道有工具可用。

        返回:
            ChatResponse。重点看两个字段：
              - tool_calls 不为空 → LLM 请求调用工具（content 是空）
              - tool_calls 为空   → content 就是最终回答
        """
        start_time = time.time()

        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            # ---- 解析工具调用请求 ----
            # 注意：arguments 从 API 返回时是"字符串"，
            # 必须 json.loads 成字典，后面才能 **arguments 传给工具函数。
            tool_calls = None
            if getattr(msg, "tool_calls", None):
                tool_calls = []
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments or "{}"),
                    })

            usage = response.usage
            return ChatResponse(
                success=True,
                content=msg.content or "",
                tool_calls=tool_calls,
                response_time=round(time.time() - start_time, 3),
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

        except Exception as e:
            # Agent 循环里任何一次 LLM 调用失败都不该让整个任务崩溃，
            # 统一返回失败结果，由 Agent 决定怎么处理。
            return ChatResponse(
                success=False,
                error=f"{type(e).__name__}: {e}",
                response_time=round(time.time() - start_time, 3),
            )

    def _fail(self, question, start_time, error, error_type):
        """构造失败的 LLMResponse，减少重复代码。"""
        return LLMResponse(
            success=False,
            question=question,
            error=error,
            error_type=error_type,
            response_time=round(time.time() - start_time, 3),
        )
