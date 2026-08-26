"""Agent Memory 分层。

短期记忆：SessionMemory 保存对话历史；LangGraph checkpoint 保存可恢复运行状态。
长期记忆：LongTermMemory 只保存明确白名单的业务事实，不保存 Token 或完整消息。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol


class SessionMemory:
    """保存不同 session 的短期对话历史。"""

    def __init__(self) -> None:
        self._sessions: dict[str, list[Any]] = defaultdict(list)

    def get(self, session_id: str) -> list[Any]:
        return list(self._sessions[session_id])

    def append(self, session_id: str, messages: list[Any]) -> None:
        self._sessions[session_id].extend(messages)

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


@dataclass(frozen=True)
class MemoryItem:
    """一条可持久化的业务记忆。"""

    key: str
    value: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class LongTermMemory(Protocol):
    """长期记忆最小接口，不绑定 Redis/DB 等具体实现。"""

    async def get(self, scope: str, key: str) -> MemoryItem | None: ...

    async def put(self, scope: str, item: MemoryItem) -> None: ...

    async def delete(self, scope: str, key: str) -> None: ...


class InMemoryLongTermMemory:
    """开发/测试实现；生产环境可以无侵入替换为 Redis/DB。"""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], MemoryItem] = {}

    async def get(self, scope: str, key: str) -> MemoryItem | None:
        return self._items.get((scope, key))

    async def put(self, scope: str, item: MemoryItem) -> None:
        self._items[(scope, item.key)] = item

    async def delete(self, scope: str, key: str) -> None:
        self._items.pop((scope, key), None)


async def load_relevant_memory(memory: LongTermMemory | None, scope: str, keys: list[str]) -> dict[str, Any]:
    """只加载 Workflow 明确需要的记忆，避免把全部历史塞给 LLM。"""
    if memory is None:
        return {}
    result: dict[str, Any] = {}
    for key in keys:
        item = await memory.get(scope, key)
        if item is not None:
            result[key] = item.value
    return result


async def save_business_memory(memory: LongTermMemory | None, scope: str, facts: dict[str, Any], keys: list[str]) -> None:
    """只保存业务事实白名单；认证 Token、消息历史等不会进入长期记忆。"""
    if memory is None:
        return
    for key in keys:
        if key in facts:
            await memory.put(scope, MemoryItem(key=key, value=facts[key]))
