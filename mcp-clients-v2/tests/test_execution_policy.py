"""Agent 执行策略测试。"""

import pytest

from agent.execution_policy import AgentExecutionPolicy


def test_default_policy_is_conservative() -> None:
    policy = AgentExecutionPolicy()
    assert policy.max_steps == 8
    assert policy.max_input_chars == 4000
    assert policy.retryable_tools == frozenset()
    policy.validate()


def test_invalid_step_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        AgentExecutionPolicy(max_steps=0).validate()


def test_invalid_input_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        AgentExecutionPolicy(max_input_chars=0).validate()
