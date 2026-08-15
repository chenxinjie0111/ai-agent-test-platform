"""
阶段四：权限测试

分两类：
  1. 单元测试（不调 LLM）—— 直接测试 check_permission 函数
     这是"第二层防御"的核心，必须 100% 确定性、不可绕过
  2. 集成测试（调 LLM）—— 验证管理员角色能正常使用敏感工具
     证明权限系统不是"一刀切禁止"，而是"按角色放行"

面试关键认知：
  AI 层面的判断不能代替真正的后端权限控制。
  这里的 check_permission 就是"真正的后端权限控制"。
"""

import pytest

from app.agent.permissions import (
    check_permission,
    is_sensitive_tool,
    ROLE_EMPLOYEE,
    ROLE_ADMIN,
    BASIC_TOOLS,
    SENSITIVE_TOOLS,
)


class TestPermissionUnit:
    """
    单元测试：直接测试 check_permission 函数。
    不需要 LLM，不需要 Agent，纯函数测试 —— 快、确定性、可重复。
    """

    def test_employee_can_use_basic_tools(self):
        """普通员工可以使用三个基础工具。"""
        for tool in BASIC_TOOLS:
            assert check_permission(ROLE_EMPLOYEE, tool) is True, (
                f"普通员工应能使用 {tool}"
            )

    def test_employee_cannot_use_sensitive_tools(self):
        """普通员工不能使用三个敏感工具。"""
        for tool in SENSITIVE_TOOLS:
            assert check_permission(ROLE_EMPLOYEE, tool) is False, (
                f"普通员工不应能使用 {tool} —— 这是安全漏洞"
            )

    def test_admin_can_use_all_tools(self):
        """管理员可以使用全部六个工具。"""
        all_tools = BASIC_TOOLS + SENSITIVE_TOOLS
        for tool in all_tools:
            assert check_permission(ROLE_ADMIN, tool) is True, (
                f"管理员应能使用 {tool}"
            )

    def test_unknown_role_no_access(self):
        """未知角色（不在权限矩阵里）不能使用任何工具。"""
        assert check_permission("guest", "weather_tool") is False
        assert check_permission("guest", "query_salary_tool") is False
        assert check_permission("", "weather_tool") is False

    def test_is_sensitive_tool(self):
        """is_sensitive_tool 正确识别敏感工具。"""
        assert is_sensitive_tool("query_salary_tool") is True
        assert is_sensitive_tool("delete_order_tool") is True
        assert is_sensitive_tool("database_admin_tool") is True
        assert is_sensitive_tool("weather_tool") is False
        assert is_sensitive_tool("calculator_tool") is False


class TestPermissionIntegration:
    """
    集成测试：验证管理员角色能正常使用敏感工具（真实调用 LLM）。
    证明权限系统是"按角色放行"，不是"一刀切禁止"。
    """

    def test_admin_can_query_salary(self, admin_agent):
        """管理员查询薪资应该成功（工具被允许执行）。"""
        result = admin_agent.run("帮我查询张三的薪资")

        # 找到 query_salary_tool 的步骤
        salary_step = None
        for step in result.trace.steps:
            if step.tool_name == "query_salary_tool":
                salary_step = step
                break

        # 断言 1：管理员调用了 query_salary_tool
        assert salary_step is not None, (
            f"管理员应该调用 query_salary_tool，"
            f"但 Trace 里没有。Steps: {[s.tool_name for s in result.trace.steps]}"
        )

        # 断言 2：工具成功执行（没有被 blocked）
        assert not salary_step.tool_result.get("blocked"), (
            f"管理员的薪资查询被错误拦截: {salary_step.tool_result}"
        )

        # 断言 3：回答里包含薪资数据（15000）
        # 格式归一化：LLM 可能把 15000 格式化成 15,000（千分位逗号）
        # 和阶段三 Final Answer 测试同一个教训：AI 测试必须考虑表达多样性
        normalized_answer = result.answer.replace(",", "")
        assert "15000" in normalized_answer, (
            f"管理员查询薪资，回答里应包含薪资数据: {result.answer}"
        )
