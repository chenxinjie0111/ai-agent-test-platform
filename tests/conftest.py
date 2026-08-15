"""
tests/conftest.py —— Pytest 公共配置

fixture（夹具）是 Pytest 的核心概念：
  一个"可复用的测试前置条件"。
  这里定义的 agent fixture，让每个测试函数都能自动拿到
  一个创建好的 Agent 实例，不用每个测试自己 new 一个。

用法：测试函数参数里写上 fixture 名即可：
    def test_xxx(agent):
        result = agent.run("...")
"""

import pytest

from app.agent.agent import Agent


@pytest.fixture
def agent():
    """返回一个普通员工角色的 Agent（默认角色）。"""
    return Agent(role="employee")


@pytest.fixture
def admin_agent():
    """返回一个管理员角色的 Agent（可使用敏感工具）。"""
    return Agent(role="admin")
