"""Agent Tool 重试策略。

重试只用于“可能瞬时恢复”的基础设施错误；业务参数错误不应该被重复提交。
具体哪些 Tool 允许重试仍由 MCPToolClient 的 retryable_tools 配置决定。
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_async(operation: Callable[[], Awaitable[T]], attempts: int, base_delay: float = 0.5) -> T:
    """最多执行 attempts+1 次，并使用简单的递增退避。

    attempts=0 表示只执行一次；重试次数由调用方控制，避免 Agent 无限重试。
    """
    if attempts < 0:
        raise ValueError("attempts must be >= 0")
    last_error: Exception | None = None
    for attempt in range(attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                raise
            await asyncio.sleep(base_delay * (attempt + 1))
    raise last_error  # pragma: no cover - loop always returns or raises
