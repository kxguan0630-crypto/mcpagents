"""Agent 对外服务层。

这一层把「一次请求」翻译成「一次 Agent 执行」。
HTTP 层不需要知道 LangGraph、MCP 或 Checkpoint 的细节。

本轮把原来的进程内 SessionMemory 替换成可插拔 Checkpoint：

    AgentService -> AgentCheckpoint -> InMemory / Redis

因此 Agent 核心不需要知道 Redis。
"""

from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage

from .checkpoint import AgentCheckpoint
from .events import AgentEvent
from .graph import build_agent_graph
from .in_memory_checkpoint import InMemoryCheckpoint
from .limits import AgentLimits
from .state import AgentState


class AgentService:
    """应用层 Agent 服务。"""

    def __init__(
        self,
        llm,
        mcp_client,
        checkpoint: AgentCheckpoint | None = None,
        limits: AgentLimits | None = None,
    ):
        self.mcp_client = mcp_client
        # 没有注入 Redis 时默认使用内存实现，方便本地学习和测试。
        self.checkpoint = checkpoint or InMemoryCheckpoint()
        self.limits = limits or AgentLimits()
        self.graph = build_agent_graph(llm, mcp_client.tools, self.limits)

    async def _build_state(self, session_id: str, user_input: str) -> AgentState:
        """从 Checkpoint 恢复历史，再加入本轮用户消息。"""
        saved_state = await self.checkpoint.load(session_id)
        history = saved_state["messages"] if saved_state else []
        return {
            "messages": [*history, HumanMessage(content=user_input)],
            "step": 0,
        }

    async def run(self, session_id: str, user_input: str) -> str:
        """执行一轮完整 Agent，并保存最终状态。"""
        state = await self._build_state(session_id, user_input)
        result = await self.graph.ainvoke(state)
        await self.checkpoint.save(session_id, result)
        return result["messages"][-1].content

    async def run_stream(
        self,
        session_id: str,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """流式执行 Agent，完成后保存最终状态。"""
        state = await self._build_state(session_id, user_input)

        try:
            async for update in self.graph.astream(state, stream_mode="updates"):
                for node_name, node_state in update.items():
                    messages = node_state.get("messages", [])

                    if node_name == "tools":
                        for message in messages:
                            yield AgentEvent(
                                type="tool_end",
                                content=str(getattr(message, "content", "")),
                                tool_name=getattr(message, "name", None),
                            )

                    elif node_name == "llm":
                        for message in messages:
                            content = getattr(message, "content", "")
                            tool_calls = getattr(message, "tool_calls", None)
                            if content and not tool_calls:
                                yield AgentEvent(type="answer", content=str(content))

            # Graph 执行成功后才持久化，避免半途异常产生不完整 checkpoint。
            final_state = await self.graph.ainvoke(state)
            await self.checkpoint.save(session_id, final_state)
            yield AgentEvent(type="done")

        except Exception as exc:
            # 不把 traceback 泄露给 API 调用方；详细日志后续放入 Observability。
            yield AgentEvent(type="error", content=str(exc))
