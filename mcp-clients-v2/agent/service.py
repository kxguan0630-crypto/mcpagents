"""Agent 对外服务层。

这一层把「一次请求」翻译成「一次 Agent 执行」。
HTTP 层不需要知道 LangGraph、MCP 或 Checkpoint 的细节。

本轮继续保持一个原则：请求校验、状态恢复、Agent 执行、状态保存、
可观测性分别有清晰职责，不把所有逻辑塞进一个函数。
"""

from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages

from .checkpoint import AgentCheckpoint
from .events import AgentEvent
from .graph import build_agent_graph
from .in_memory_checkpoint import InMemoryCheckpoint
from .limits import AgentLimits
from .observability import AgentRunTracker
from .state import AgentState
from .input_validation import validate_agent_input


class AgentService:
    """应用层 Agent 服务。"""

    def __init__(
        self,
        llm,
        mcp_client,
        checkpoint: AgentCheckpoint | None = None,
        limits: AgentLimits | None = None,
        tracker: AgentRunTracker | None = None,
    ):
        self.mcp_client = mcp_client
        self.checkpoint = checkpoint or InMemoryCheckpoint()
        self.limits = limits or AgentLimits()
        self.limits.validate()
        self.tracker = tracker or AgentRunTracker()
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
        validate_agent_input(session_id, user_input)

        run = self.tracker.start(session_id)
        try:
            state = await self._build_state(session_id, user_input)
            result = await self.graph.ainvoke(state)
            await self.checkpoint.save(session_id, result)
            self.tracker.finish(run, "success")
            return result["messages"][-1].content
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            raise

    async def run_stream(
        self,
        session_id: str,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """流式执行 Agent，并在成功结束后保存最终状态。"""
        validate_agent_input(session_id, user_input)

        run = self.tracker.start(session_id)
        state = await self._build_state(session_id, user_input)
        final_state: AgentState = {
            "messages": list(state["messages"]),
            "step": state["step"],
        }

        try:
            async for update in self.graph.astream(state, stream_mode="updates"):
                for node_name, node_state in update.items():
                    messages = node_state.get("messages", [])
                    final_state["messages"] = add_messages(
                        final_state["messages"], messages
                    )
                    if "step" in node_state:
                        final_state["step"] = node_state["step"]

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

            await self.checkpoint.save(session_id, final_state)
            self.tracker.finish(run, "success")
            yield AgentEvent(type="done")
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            yield AgentEvent(type="error", content="Agent execution failed")
