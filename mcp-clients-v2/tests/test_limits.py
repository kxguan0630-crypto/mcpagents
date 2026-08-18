"""Agent 限制的最小单元测试。

这些测试不启动 LLM 或 MCP Server，所以运行很快。
"""

import pytest

from agent.limits import AgentLimits


def test_default_limits_are_safe():
    """默认配置应该允许有限的 Agent 循环。"""
    limits = AgentLimits()
    limits.validate()
    assert limits.max_steps == 8
    assert limits.max_tool_retries == 2


def test_invalid_step_limit_is_rejected():
    """明显错误的限制应该在启动阶段被发现。"""
    with pytest.raises(ValueError):
        AgentLimits(max_steps=0).validate()
