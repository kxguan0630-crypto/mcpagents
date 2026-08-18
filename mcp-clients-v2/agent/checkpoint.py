"""Agent Checkpoint 抽象。

为什么单独做这一层？
--------------------
Agent 本身只关心「我要保存/恢复什么状态」，不应该关心状态到底
存在内存、Redis 还是数据库。

因此先定义一个非常简单的接口：

    session_id -> AgentState

下一步 Redis 只需要实现这个接口即可。
"""

from abc import ABC, abstractmethod

from .state import AgentState


class AgentCheckpoint(ABC):
    """保存和恢复 Agent 状态的统一接口。"""

    @abstractmethod
    async def load(self, session_id: str) -> AgentState | None:
        """读取指定 session 最近一次保存的 Agent 状态。"""
        raise NotImplementedError

    @abstractmethod
    async def save(self, session_id: str, state: AgentState) -> None:
        """保存指定 session 的 Agent 状态。"""
        raise NotImplementedError

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """删除指定 session 的 checkpoint。"""
        raise NotImplementedError
