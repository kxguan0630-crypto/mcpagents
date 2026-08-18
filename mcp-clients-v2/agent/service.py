"""Agent 对外服务层。

这一层把「一次请求」翻译成「一次 Agent 执行」。
HTTP 层不需要知道 LangGraph、MCP 或 Memory 的细节。

本轮新增 run_stream()：
- 普通调用继续使用 run()。
- SSE/流式接口使用 run_stream()。
- API 层只消费 AgentEvent，不直接理解 LangGraph 内部事件。
"""

from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage

from .events import AgentEvent
from .graph import build_agent_graph
from .limits import AgentLimits
from .memory import SessionMemory
from .state import AgentState


class AgentService:
    """应用层 Agent 服务。"""

    def __init__(
        self,
        llm,
        mcp_client,
        memory: SessionMemory | None = None,
        limits: AgentLimits | None = None,
    ):
        self.mcp_client = mcp_client
        self.memory = memory or SessionMemory()
        self.limits = limits or AgentLimits()
        self.graph = build_agent_graph(llm, mcp_client.tools, self.limits)

    def _build_state(self, session_id: str, user_input: str) -> AgentState:
        """从 Session Memory 构造一次 Agent 执行的初始状态。"""
        history = self.memory.get(session_id)
        return {
            "messages": [*history, HumanMessage(content=user_input)],
            "step": 0,
        }

    async def run(self, session_id: str, user_input: str) -> str:
        """执行一轮完整 Agent，并保存新增消息。"""
        history = self.memory.get(session_id)
        state = self._build_state(session_id, user_input)

        result = await self.graph.ainvoke(state)
        new_messages = result["messages"][len(history):]
        self.memory.append(session_id, new_messages)

        return result["messages"][-1].content

    async def run_stream(
        self,
        session_id: str,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """以事件流执行 Agent。

        注意：这里不把 LangGraph 的原始事件直接暴露给客户端。
        我们只输出自己的 AgentEvent，这样未来更换 Graph 实现时 API 不需要改。
        """
        history = self.memory.get(session_id)
        state = self._build_state(session_id, user_input)
        all_messages = []

        try:
            async for update in self.graph.astream(state, stream_mode="updates"):
                # update 的 key 是 graph node 名，例如 llm / tools。
                for node_name, node_state in update.items():
                    messages = node_state.get("messages", [])
                    all_messages.extend(messages)

                    if node_name == "tools":
                        # 工具执行结束后，LangGraph 会产生 ToolMessage。
                        for message in messages:
                            tool_name = getattr(message, "name", None)
                            yield AgentEvent(
                                type="tool_end",
                                content=str(getattr(message, "content", "")),
                                tool_name=tool_name,
                            )

                    elif node_name == "llm":
                        for message in messages:
                            # 模型准备调用工具时通常 content 为空。
                            # 只有真正的自然语言内容才作为 answer 推给前端。
                            content = getattr(message, "content", "")
                            tool_calls = getattr(message, "tool_calls", None)
                            if content and not tool_calls:
                                yield AgentEvent(type="answer", content=str(content))

            # 本轮完成后再一次性保存，避免半途失败污染 Session Memory。
            self.memory.append(session_id, [*state["messages"][len(history):], *all_messages])
            yield AgentEvent(type="done")

        except Exception as exc:
            # 对外只暴露清晰错误，不把 Python traceback 泄露给客户端。
            yield AgentEvent(type="error", content=str(exc))
