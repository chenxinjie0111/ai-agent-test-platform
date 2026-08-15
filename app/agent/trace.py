"""
Agent Trace：记录 Agent 执行过程的每一步

Trace 就是 Agent 的黑匣子：每一次 LLM 决策、每一次工具调用、
每一个参数、每一条结果，全部留痕。
"""

from dataclasses import dataclass, field, asdict


@dataclass
class TraceStep:
    """
    一次工具调用步骤。
    """
    round: int                  # 第几轮循环（1 开始）
    tool_name: str              # 调用了哪个工具
    tool_arguments: dict        # 传入的参数
    tool_result: dict           # 工具的返回结果（含错误时也是 dict）
    response_time: float = 0.0  # 本轮 LLM 调用耗时

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentTrace:
    """一次完整 Agent 任务的执行记录。"""
    user_input: str             # 用户输入
    steps: list = field(default_factory=list)   # 工具调用步骤列表
    final_answer: str = ""      # 最终回答
    success: bool = False       # 任务是否成功
    total_time: float = 0.0     # 任务总耗时（秒）
    total_tokens: int = 0       # 任务总 token 消耗
    num_llm_calls: int = 0      # LLM 被调用了多少次（= 循环轮数）
    error: str = ""             # 失败原因（成功时为空）

    def to_dict(self) -> dict:
        """转成 JSON 可序列化字典 —— 后面写测试报告 / Web 展示都靠它。"""
        return {
            "user_input": self.user_input,
            "steps": [s.to_dict() for s in self.steps],
            "final_answer": self.final_answer,
            "success": self.success,
            "total_time": self.total_time,
            "total_tokens": self.total_tokens,
            "num_llm_calls": self.num_llm_calls,
            "num_tool_calls": len(self.steps),
            "error": self.error,
        }

    def pretty_print(self):
        """终端友好展示。"""
        print(f"  用户输入     : {self.user_input}")
        for s in self.steps:
            print(f"  第 {s.round} 轮 -> {s.tool_name}({s.tool_arguments})")
            print(f"     工具结果 : {s.tool_result}")
        print(f"  最终回答     : {self.final_answer}")
        print(f"  任务状态     : {'成功' if self.success else '失败'}")
        print(f"  总耗时       : {self.total_time}s | LLM 调用 {self.num_llm_calls} 次 "
              f"| 工具调用 {len(self.steps)} 次 | 总 token {self.total_tokens}")
