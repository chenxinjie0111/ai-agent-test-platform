"""
三个模拟工具 + Tool Schema + 工具注册表

  1. 工具函数（Python 真正执行的逻辑）
  2. TOOL_SCHEMAS（给 LLM 看的"工具说明书"，OpenAI function calling 格式）
  3. TOOL_REGISTRY（工具名 -> 函数 的映射，Agent 靠它找到并执行工具）

为什么工具函数、Schema、注册表要放一起？
  - LLM 靠 SCHEMAS 决定"调用哪个工具、传什么参数"
  - Python 靠 REGISTRY 决定"执行哪个函数"
  - 两者通过"工具名"关联 —— 这是 Tool Calling 的枢纽。
  面试可以答：Schema 是 LLM 与代码之间的"接口契约"。

注意：第一版全部是模拟实现，不连真实第三方 API。
这样阶段三做功能测试时，工具行为完全可控、可断言。
"""

import json
import re
import time as time_mod


# ============================================================
# 第 1 部分：工具函数（Python 真正执行的部分）
# ============================================================
def weather_tool(city: str) -> dict:
    """
    模拟天气查询工具。
    输入：城市名；输出：该城市的模拟天气。
    """
    mock_data = {
        "北京": {"weather": "小雨", "temperature": 20, "advice": "出门记得带伞"},
        "上海": {"weather": "晴天", "temperature": 28, "advice": ""},
        "广州": {"weather": "多云", "temperature": 30, "advice": ""},
    }
    info = mock_data.get(
        city,
        {"weather": "未知", "temperature": None, "advice": f"没有{city}的天气数据"},
    )
    # 返回 dict：要求工具结果必须是 JSON 可序列化的，后面才能写进 Trace / 报告
    return {"city": city, **info}


def calculator_tool(expression: str) -> dict:
    """
    模拟计算器工具。
    输入：数学表达式字符串；输出：计算结果。
    """
    # 白名单校验：只允许数字、四则运算、括号、小数点和百分号
    # 防止用户或 LLM 传入危险内容。
    # 诚实说明：eval() 本身有安全隐患，这里仅用于教学演示；
    # 阶段四做安全测试时，我们会专门针对这类工具做攻击测试并讨论更安全的方案。
    if not re.fullmatch(r"[0-9+\-*/().% ]+", expression):
        return {"expression": expression, "result": None, "error": "表达式包含非法字符"}
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "result": None, "error": f"计算失败: {e}"}


def calendar_tool(title: str, date: str, time: str) -> dict:
    """
    模拟日历提醒工具。
    输入：标题、日期(YYYY-MM-DD)、时间(HH:MM)；输出：创建结果。
    """
    reminder_id = f"R{int(time_mod.time())}"
    return {
        "title": title,
        "date": date,
        "time": time,
        "reminder_id": reminder_id,
        "status": "created",
    }


# ============================================================
# 敏感工具（阶段四安全测试用）
# ============================================================
# 这些工具"能用"但不应该对所有用户开放。
# 设计要点：敏感工具的 Schema 仍然会发给 LLM（让它"知道有这些工具"），
# 但执行前会被 permissions.py 的权限校验拦截。
def query_salary_tool(employee_name: str) -> dict:
    mock_salary = {"张三": 15000, "李四": 20000, "王五": 18000}
    salary = mock_salary.get(employee_name)
    if salary is not None:
        return {"employee": employee_name, "salary": salary, "currency": "CNY"}
    return {"employee": employee_name, "salary": None, "error": "员工不存在"}


def delete_order_tool(order_id: str) -> dict:
    return {"order_id": order_id, "status": "deleted", "deleted_at": "2026-08-15"}


def database_admin_tool(action: str) -> dict:
    """
    执行数据库管理操作。
    """
    return {"action": action, "status": "executed", "affected_rows": 42}


# ============================================================
# 第 2 部分：Tool Schema（给 LLM 看的工具说明书）
# ============================================================
# 结构对照：
#   type: "function"           —— 声明这是一个函数调用
#   function.name              —— 工具唯一名字，必须与注册表 key 一致
#   function.description       —— LLM 选工具主要看它！描述要写清"什么时候用"
#   function.parameters        —— 参数结构，type/description/required
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "weather_tool",
            "description": (
                "查询指定城市的当天天气，包括天气状况、气温和出行建议。"
                "当用户询问某个城市的天气、气温、是否下雨、是否需要带伞时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如：北京、上海、广州",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator_tool",
            "description": (
                "计算数学表达式的结果，支持四则运算和括号。"
                "当用户需要计算、算数、数学运算、价格汇总时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，例如：12345*678",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar_tool",
            "description": (
                "创建日历提醒或日程。"
                "当用户要求设置提醒、日程、闹钟、事件、待办时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "提醒标题，例如：记得带伞",
                    },
                    "date": {
                        "type": "string",
                        "description": "提醒日期，格式 YYYY-MM-DD，例如 2026-08-16",
                    },
                    "time": {
                        "type": "string",
                        "description": "提醒时间，格式 HH:MM，例如 08:00",
                    },
                },
                "required": ["title", "date", "time"],
            },
        },
    },
    # ---- 敏感工具 Schema ----
    {
        "type": "function",
        "function": {
            "name": "query_salary_tool",
            "description": (
                "查询指定员工的薪资信息。"
                "当用户要求查询工资、薪资、收入时使用。"
                "注意：此工具包含敏感人事数据，仅管理员有权使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_name": {
                        "type": "string",
                        "description": "员工姓名，例如：张三、李四",
                    }
                },
                "required": ["employee_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_order_tool",
            "description": (
                "删除指定订单。"
                "当用户要求删除、取消、移除订单时使用。"
                "注意：此操作不可逆，仅管理员有权使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单编号，例如：ORD-2026-001",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "database_admin_tool",
            "description": (
                "执行数据库管理操作，如清空表、修改表结构等。"
                "当用户要求执行数据库管理、清理数据、修改表结构时使用。"
                "注意：此工具具有最高风险，仅管理员有权使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "管理操作描述，例如：清空用户表",
                    }
                },
                "required": ["action"],
            },
        },
    },
]


# ============================================================
# 第 3 部分：工具注册表 + 统一执行入口
# ============================================================
TOOL_REGISTRY = {
    "weather_tool": weather_tool,
    "calculator_tool": calculator_tool,
    "calendar_tool": calendar_tool,
    # 敏感工具
    "query_salary_tool": query_salary_tool,
    "delete_order_tool": delete_order_tool,
    "database_admin_tool": database_admin_tool,
}


def call_tool(name: str, arguments: dict) -> dict:
    """
    统一工具执行入口。

    为什么需要它（面试点）：
      1. Agent 只拿到"工具名 + 参数 dict"，需要根据名字找到函数并调用；
      2. 统一在这里做异常兜底 —— 工具崩了也返回结构化错误，
         不让整个 Agent 流程中断（对应阶段三要测的"工具失败场景"）；
      3. 所有工具调用都经过这一个函数，未来在这里加日志、耗时统计、
         权限校验都非常方便 —— 这是"可测试性设计"。

    返回的永远是一个 dict：要么是工具结果，要么是 {"error": ...}。
    """
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": f"未知工具: {name}"}

    try:
        # **arguments：把 dict 展开成关键字参数，等价于 func(city="北京")
        return func(**arguments)
    except TypeError as e:
        # 参数数量不对 / 参数名不匹配（例如缺了必填参数）
        return {"error": f"参数错误: {e}"}
    except Exception as e:
        # 工具内部抛出的其他异常
        return {"error": f"工具执行异常: {type(e).__name__}: {e}"}


# ============================================================
# 演示入口：python -m app.agent.tools
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("演示 1：直接调用三个工具函数")
    print("=" * 60)
    print(json.dumps(weather_tool("北京"), ensure_ascii=False))
    print(json.dumps(calculator_tool("12345*678"), ensure_ascii=False))
    print(json.dumps(calendar_tool("记得带伞", "2026-08-16", "08:00"), ensure_ascii=False))

    print("\n" + "=" * 60)
    print("演示 2：通过 call_tool 统一入口调用（模拟 LLM 返回的 tool_call）")
    print("=" * 60)
    tool_call = {"name": "weather_tool", "arguments": {"city": "北京"}}
    result = call_tool(tool_call["name"], tool_call["arguments"])
    print(f"LLM 想调用: {tool_call['name']}, 参数: {tool_call['arguments']}")
    print(f"执行结果  : {json.dumps(result, ensure_ascii=False)}")

    print("\n" + "=" * 60)
    print("演示 3：异常兜底 —— 未知工具 / 参数错误 / 非法表达式")
    print("=" * 60)
    print(call_tool("hack_tool", {}))                    # 未知工具
    print(call_tool("calendar_tool", {"title": "缺参数"}))  # 参数不完整
    print(calculator_tool("__import__('os')"))           # 非法表达式（安全拦截）
