"""
阶段四：异常输入测试

测试目标：验证 Agent 面对异常输入时不会崩溃，能优雅处理。

断言策略：
  - 不断言"回答正确"（异常输入本就没有标准答案）
  - 只断言"Agent 正常返回了结果"（没有崩溃）
  - 附加断言：结果对象结构完整（有 answer、有 trace）
"""

import pytest


class TestExceptionInput:
    """异常输入测试：Agent 不能因为输入异常而崩溃。"""
    def test_empty_input(self, agent):
        """
        空输入
        期望：Agent 不崩溃，返回某种结果（可能是错误提示或默认回复）。
        """
        result = agent.run("")

        # 断言：Agent 返回了结果对象（没崩溃）
        assert result is not None
        assert result.trace is not None
        # 回答可以是任何内容，但不能是 None
        assert result.answer is not None

    def test_super_long_input(self, agent):
        """
        超长输入
        期望：Agent 不崩溃（可能因 token 超限返回错误，但不能抛异常）。
        """
        # 生成一个很长的输入
        long_input = "请帮我查一下北京天气。" + "今天天气真好啊。" * 300

        result = agent.run(long_input)

        # 断言：Agent 正常返回了
        assert result is not None
        assert result.trace is not None
        assert result.answer is not None

    def test_special_characters(self, agent):
        """
        特殊字符
        期望：Agent 不崩溃，能理解或至少不报错。
        """
        special_input = "@#$%^&*()_+-=[]{}|;':\",./<>?`~"

        result = agent.run(special_input)

        # 断言：Agent 正常返回
        assert result is not None
        assert result.trace is not None
        assert result.answer is not None

    def test_mixed_multiple_tasks(self, agent):
        """
        混合任务：用户一条消息里塞了多个不同任务。
        期望：Agent 能处理（至少完成部分），不崩溃。
        这也是阶段三 Workflow 测试的"混乱版"。
        """
        mixed_input = (
            "帮我做三件事："
            "第一，查北京天气；"
            "第二，计算 999 乘以 888；"
            "第三，帮我创建一个明天下午3点的'项目评审会'提醒。"
        )

        result = agent.run(mixed_input)

        # 断言：Agent 正常返回了
        assert result is not None
        assert result.trace is not None

        # 断言：Agent 至少调用了工具（尝试处理任务）
        # 可能不会一次全做完，但至少应该在尝试
        assert len(result.trace.steps) > 0, (
            f"混合任务应该触发工具调用，但 Trace 为空。Answer: {result.answer}"
        )

    def test_fuzzy_vague_instruction(self, agent):
        """
        模糊指令：用户说的话含糊不清。
        期望：Agent 不崩溃，可以询问澄清或做合理猜测。
        """
        vague_input = "那个东西帮我弄一下"

        result = agent.run(vague_input)

        # 断言：Agent 正常返回了
        assert result is not None
        assert result.trace is not None
        assert result.answer is not None
