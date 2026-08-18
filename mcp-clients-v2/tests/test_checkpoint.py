"""Checkpoint 的最小测试。

测试重点不是 Redis 本身，而是保证所有 Checkpoint 实现遵守同一套行为：

    save -> load -> clear
"""

import pytest
from langchain_core.messages import HumanMessage

from agent.in_memory_checkpoint import InMemoryCheckpoint
from agent.redis_checkpoint import RedisCheckpoint


@pytest.mark.asyncio
async def test_in_memory_checkpoint_round_trip():
    checkpoint = InMemoryCheckpoint()
    state = {"messages": [HumanMessage(content="你好")], "step": 2}

    await checkpoint.save("session-1", state)
    loaded = await checkpoint.load("session-1")

    assert loaded is not None
    assert loaded["step"] == 2
    assert loaded["messages"][0].content == "你好"

    await checkpoint.clear("session-1")
    assert await checkpoint.load("session-1") is None


class FakeRedis:
    """测试 RedisCheckpoint 时使用的最小异步 Redis 假对象。"""

    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


@pytest.mark.asyncio
async def test_redis_checkpoint_round_trip_without_real_redis():
    redis = FakeRedis()
    checkpoint = RedisCheckpoint(redis, ttl_seconds=60)
    state = {"messages": [HumanMessage(content="hello")], "step": 3}

    await checkpoint.save("session-2", state)
    loaded = await checkpoint.load("session-2")

    assert loaded is not None
    assert loaded["step"] == 3
    assert loaded["messages"][0].content == "hello"

    await checkpoint.clear("session-2")
    assert await checkpoint.load("session-2") is None
