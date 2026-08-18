"""开发和测试使用的内存版 Checkpoint。

它不依赖 Redis，所以你可以先理解 Checkpoint 的工作方式。
生产环境再把实现替换成 RedisCheckpoint。
"""

from .checkpoint import AgentCheckpoint
from .state import AgentState


class InMemoryCheckpoint(AgentCheckpoint):
    """把最近一次 AgentState 保存在当前进程内。"""

    def __init__(self) -> None:
        self._states: dict[str, AgentState] = {}

    async def load(self, session_id: str) -> AgentState | None:
        """读取状态；返回副本，避免调用方意外修改内部数据。"""
        state = self._states.get(session_id)
        if state is None:
            return None
        return dict(state)

    async def save(self, session_id: str, state: AgentState) -> None:
        """保存最近一次状态。"""
        self._states[session_id] = dict(state)

    async def clear(self, session_id: str) -> None:
        """删除状态。"""
        self._states.pop(session_id, None)
