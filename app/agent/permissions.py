"""
权限系统：角色 -> 允许使用的工具 映射 + 权限校验函数

这是 Agent 的"第二层防御"（代码层防御）。
"""


# ============================================================
# 角色定义
# ============================================================
ROLE_EMPLOYEE = "employee"   # 普通员工
ROLE_ADMIN = "admin"         # 管理员

ALL_ROLES = [ROLE_EMPLOYEE, ROLE_ADMIN]


# ============================================================
# 权限矩阵：每个角色允许使用哪些工具
# ============================================================
# 设计要点：
#   1. 普通员工只能用三个基础工具（天气、计算器、日历）
#   2. 管理员可以额外使用三个敏感工具（薪资、删订单、数据库管理）
#   3. 敏感工具单独列出，方便测试和维护
BASIC_TOOLS = ["weather_tool", "calculator_tool", "calendar_tool"]
SENSITIVE_TOOLS = ["query_salary_tool", "delete_order_tool", "database_admin_tool"]

ROLE_PERMISSIONS = {
    ROLE_EMPLOYEE: BASIC_TOOLS,                           # 3 个基础工具
    ROLE_ADMIN: BASIC_TOOLS + SENSITIVE_TOOLS,             # 全部 6 个工具
}


def check_permission(role: str, tool_name: str) -> bool:
    """
    检查指定角色是否有权使用指定工具。

    参数:
        role: 用户角色（"employee" 或 "admin"）
        tool_name: 工具名称

    返回:
        True = 允许使用, False = 权限不足

    为什么单独抽成函数（而不是直接在 agent.py 里写 if）：
      1. 可以独立单元测试 —— 不需要调 LLM 就能验证权限逻辑
      2. 权限规则集中管理 —— 加角色、改权限只改这一个文件
      3. 未来扩展方便 —— 比如加"部门级权限"、"时间段限制"
    """
    allowed = ROLE_PERMISSIONS.get(role, [])
    return tool_name in allowed


def is_sensitive_tool(tool_name: str) -> bool:
    """判断一个工具是否是敏感工具。"""
    return tool_name in SENSITIVE_TOOLS


def get_role_description(role: str) -> str:
    """返回角色的中文描述，用于注入 System Prompt（第一层防御）。"""
    if role == ROLE_ADMIN:
        return (
            "管理员 — 可以使用所有功能，包括查询员工薪资、删除订单、"
            "数据库管理等敏感操作。"
        )
    return (
        "普通员工 — 只能使用天气查询、计算器、日历提醒功能。"
        "不能查询其他员工薪资、不能删除订单、不能执行数据库管理操作。"
        "如果用户请求超出权限的操作，请明确告知用户权限不足，不要尝试调用敏感工具。"
    )
