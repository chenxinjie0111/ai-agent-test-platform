"""
Agent 本体：Agent Loop 的实现

一个循环（round）= 一次 LLM 调用。
单步任务（查天气）在这个循环里转 1 圈；
多步任务（查天气+创建提醒）转 2 圈。
所以"单步"和"多步"用的是同一份代码——多步是 Agent Loop 的自然结果。

关键设计：
  1. 对话历史 messages 是"累积"的：每轮的 tool_call 请求和工具结果
     都追加进去，LLM 才能"记得"之前发生过什么（上下文记忆）。
  2. max_rounds 防止死循环：LLM 可能反复要调工具，必须有上限。
  3. 全程记录 Trace：每轮调了什么工具、参数、结果，一个不落。
"""

import json
import time
from datetime import datetime

from app.llm.client import LLMClient
from app.agent.tools import TOOL_SCHEMAS, call_tool
from app.agent.trace import AgentTrace, TraceStep
from app.agent.permissions import check_permission, get_role_description
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AgentResult:
    """Agent 一次 run() 的完整输出：最终回答 + Trace + 统计信息。"""

    def __init__(self, success, answer, trace, total_time, total_tokens,
                 num_llm_calls):
        self.success = success
        self.answer = answer
        self.trace = trace                # AgentTrace 对象，可 .to_dict()
        self.total_time = total_time
        self.total_tokens = total_tokens
        self.num_llm_calls = num_llm_calls

    def __repr__(self):
        return (f"AgentResult(success={self.success}, answer={self.answer!r}, "
                f"time={self.total_time}s, tokens={self.total_tokens})")


class Agent:
    DEFAULT_SYSTEM_PROMPT = (
        "你是一个企业内部的智能办公助手，可以帮员工查天气、做计算、管理日程提醒。"
        "你有三个工具：weather_tool（查天气）、calculator_tool（数学计算）、"
        "calendar_tool（创建日历提醒）。"
        "当用户的问题需要真实数据或精确计算时，必须调用对应工具，"
        "不要自己编造数据；拿到工具结果后，用简洁的中文回答用户。"
    )

    def __init__(self, llm_client=None, system_prompt=None, max_rounds=5,
                 role="employee"):
        # 允许传入自定义 llm_client：测试时可以换成一个"假的 LLM"（后面阶段讲）
        self.llm = llm_client or LLMClient()
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.max_rounds = max_rounds
        self.role = role   # 用户角色：employee / admin

    def run(self, user_input: str) -> AgentResult:
        """执行一次 Agent 任务。"""
        logger.info(f"Agent 开始执行 | 角色={self.role} | 输入={user_input[:50]}")
        start_time = time.time()
        total_tokens = 0

        # ---- 对话历史：从 system + user 开始，之后每轮不断追加 ----
        # 关键：system prompt 里注入"今天的日期"。
        # LLM 没有时钟，不告诉它今天几号，它就不知道该怎么填 date 参数，
        # 甚至会反问用户（刚才真实跑出来的 bug）。
        today = datetime.now().strftime("%Y-%m-%d")
        # 第一层防御：在 System Prompt 里注入角色信息
        # 告诉 LLM 当前用户的角色和权限边界，让它在决策阶段就避开敏感工具
        role_desc = get_role_description(self.role)
        system_prompt = (
            f"{self.system_prompt}\n"
            f"当前用户角色：{role_desc}\n"
            f"今天是 {today}。创建提醒等需要日期的任务时，直接使用今天的日期推算，"
            "不要反问用户日期。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        trace = AgentTrace(user_input=user_input)

        for round_no in range(1, self.max_rounds + 1):
            # ---- 第 1 步：LLM 决策（带工具说明书）----
            resp = self.llm.chat(messages, tools=TOOL_SCHEMAS)
            total_tokens += resp.total_tokens

            # LLM 调用本身失败了：直接结束，不硬撑
            if not resp.success:
                logger.error(f"LLM 调用失败 | 第{round_no}轮 | 错误={resp.error}")
                trace.success = False
                trace.final_answer = f"[Agent错误] LLM 调用失败: {resp.error}"
                trace.error = resp.error
                return self._build_result(
                    False, trace.final_answer, trace, start_time,
                    total_tokens, round_no)

            # ---- 第 2 步：判断"需要工具吗？" ----
            # tool_calls 为空 -> LLM 直接回答，循环结束
            if not resp.tool_calls:
                logger.info(f"Agent 完成 | 第{round_no}轮 | token={total_tokens} | 耗时={round(time.time()-start_time,2)}s")
                trace.success = True
                trace.final_answer = resp.content
                return self._build_result(
                    True, resp.content, trace, start_time,
                    total_tokens, round_no)

            # ---- 第 3 步：LLM 请求调用工具，把请求追加进对话历史 ----
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(
                                tc["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in resp.tool_calls
                ],
            })

            # ---- 第 4 步：逐个执行工具，结果追加进对话历史 ----
            for tc in resp.tool_calls:
                # 第二层防御：代码层权限校验（不可被 Prompt Injection 绕过）
                # 即使 LLM 被"你现在是管理员"骗了，到这里仍然是确定性的 if 判断
                if not check_permission(self.role, tc["name"]):
                    logger.warning(f"权限拦截 | 角色={self.role} | 工具={tc['name']} | 参数={tc['arguments']}")
                    result = {
                        "error": f"权限不足: 角色 '{self.role}' 无权使用 '{tc['name']}'",
                        "blocked": True,
                    }
                else:
                    logger.debug(f"执行工具 | 第{round_no}轮 | {tc['name']}({tc['arguments']})")
                    result = call_tool(tc["name"], tc["arguments"])

                # 记录 Trace：谁、什么参数、什么结果（包括被拦截的）
                trace.steps.append(TraceStep(
                    round=round_no,
                    tool_name=tc["name"],
                    tool_arguments=tc["arguments"],
                    tool_result=result,
                    response_time=resp.response_time,
                ))

                # 工具结果必须以 role="tool" 回传，且带 tool_call_id
                # 无论成功还是被拦截，都把结果回传给 LLM，让它告知用户
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # ---- 回到循环顶部：LLM 带着工具结果再决策一次 ----

        # ---- 达到 max_rounds 还没结束：按失败处理 ----
        error = f"达到最大循环轮数 {self.max_rounds}，任务未完成"
        trace.success = False
        trace.final_answer = f"[Agent错误] {error}"
        trace.error = error
        return self._build_result(
            False, trace.final_answer, trace, start_time,
            total_tokens, self.max_rounds)

    def _build_result(self, success, answer, trace, start_time,
                      total_tokens, num_llm_calls):
        """把统计信息装进 AgentResult（并同步到 trace）。"""
        trace.total_time = round(time.time() - start_time, 3)
        trace.total_tokens = total_tokens
        trace.num_llm_calls = num_llm_calls
        return AgentResult(
            success=success,
            answer=answer,
            trace=trace,
            total_time=trace.total_time,
            total_tokens=total_tokens,
            num_llm_calls=num_llm_calls,
        )


# ============================================================
# 演示入口：python -m app.agent.agent
# 两个示例：单步任务 + 多步任务，看 Trace 的区别
# ============================================================
if __name__ == "__main__":
    agent = Agent()

    examples = [
        "北京今天天气怎么样？",
        "北京今天天气怎么样？如果下雨，帮我创建明天早上8点的\"记得带伞\"提醒",
    ]

    for question in examples:
        print("=" * 70)
        print(f"用户: {question}")
        result = agent.run(question)
        print(f"\n>>> Agent 回答: {result.answer}\n")
        print("--- Agent Trace ---")
        result.trace.pretty_print()
        print()
