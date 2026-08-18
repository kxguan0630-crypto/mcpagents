"""会话记忆层。

第一版只定义一个很容易理解的接口：

    session_id -> 消息历史

现在使用进程内内存，目的是先把 Agent 架构讲清楚。
以后切 Redis 时，只需要替换这个类，不需要修改 Agent Graph。
"""

from collections import defaultdict
from typing import Any


class SessionMemory:
    """保存不同 session 的对话消息。"""

    def __init__(self) -> None:
        # key 是 session_id，value 是 LangChain message 列表。
        self._sessions: dict[str, list[Any]] = defaultdict(list)

    def get(self, session_id: str) -> list[Any]:
        """读取一个会话的历史消息。"""
        return list(self._sessions[session_id])

    def append(self, session_id: str, messages: list[Any]) -> None:
        """把本轮产生的消息追加到会话历史。"""
        self._sessions[session_id].extend(messages)

    def clear(self, session_id: str) -> None:
        """删除指定会话，主要用于测试和登出场景。"""
        self._sessions.pop(session_id, None)
