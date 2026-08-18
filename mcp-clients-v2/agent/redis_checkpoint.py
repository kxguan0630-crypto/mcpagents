"""Redis 版 Agent Checkpoint。

这里故意不用复杂的 Redis 数据结构：

    agent:checkpoint:<session_id> -> JSON

这样你读代码时可以非常直观地看到「一个 session 对应一个状态」。

注意：Redis 只负责持久化状态，不负责 Agent 决策，也不负责 MCP Tool 调用。
"""

import json
from typing import Any

from .checkpoint import AgentCheckpoint
from .message_codec import messages_from_json_data, messages_to_json_data
from .state import AgentState


class RedisCheckpoint(AgentCheckpoint):
    """使用 Redis 保存 AgentState。"""

    def __init__(self, redis_client: Any, ttl_seconds: int = 3600) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        """统一生成 Redis key，避免项目不同地方出现不同命名规则。"""
        return f"agent:checkpoint:{session_id}"

    async def load(self, session_id: str) -> AgentState | None:
        """从 Redis 读取 JSON，并把消息恢复成 LangChain Message。"""
        raw = await self.redis.get(self._key(session_id))
        if raw is None:
            return None

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        data = json.loads(raw)
        data["messages"] = messages_from_json_data(data.get("messages", []))
        return data

    async def save(self, session_id: str, state: AgentState) -> None:
        """把 AgentState 转成 JSON 保存，并刷新 TTL。"""
        data = {
            "messages": messages_to_json_data(state.get("messages", [])),
            "step": state.get("step", 0),
        }
        await self.redis.set(
            self._key(session_id),
            json.dumps(data, ensure_ascii=False),
            ex=self.ttl_seconds,
        )

    async def clear(self, session_id: str) -> None:
        """删除 Redis 中的 checkpoint。"""
        await self.redis.delete(self._key(session_id))
