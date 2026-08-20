"""Agent Runtime 的认证上下文。

认证信息属于一次请求的运行时上下文，不属于 AgentState，也不应该进入 LLM 消息。
使用 ContextVar 让 LangGraph 在当前异步执行链里读取已经验证过的身份信息。
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuthContext:
    """一次 Agent 请求对应的认证身份。"""

    authorization: str
    user_info: dict[str, Any] = field(default_factory=dict)


_current_auth: ContextVar[AuthContext | None] = ContextVar("agent_auth_context", default=None)


def set_auth_context(context: AuthContext):
    """设置当前异步执行链的认证上下文，并返回可用于恢复的 token。"""
    return _current_auth.set(context)


def reset_auth_context(token) -> None:
    """恢复进入当前请求前的认证上下文。"""
    _current_auth.reset(token)


def get_auth_context() -> AuthContext:
    """读取当前请求认证上下文；没有认证上下文时立即失败。"""
    context = _current_auth.get()
    if context is None:
        raise RuntimeError("Agent authentication context is not available")
    return context
