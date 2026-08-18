"""输入校验的最小单元测试。

这些测试故意简单，让你可以直接看懂 Agent 在进入模型前检查了什么。
"""

import pytest

from agent.input_validation import AgentInputError, validate_agent_input


def test_valid_input() -> None:
    validate_agent_input("session-1", "查询一下患者")


def test_empty_session_is_rejected() -> None:
    with pytest.raises(AgentInputError):
        validate_agent_input("", "你好")


def test_empty_message_is_rejected() -> None:
    with pytest.raises(AgentInputError):
        validate_agent_input("session-1", "   ")


def test_oversized_message_is_rejected() -> None:
    with pytest.raises(AgentInputError):
        validate_agent_input("session-1", "a" * 11, max_chars=10)
