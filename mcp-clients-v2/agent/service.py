"""Agent 对外服务层。

这一层把「一次请求」翻译成「一次 Agent 执行」。
HTTP 层不需要知道 LangGraph、MCP 或 Memory 的细节。
"""

from langchain_core.messages import HumanMessage

from .graph import build_agent_graph
from .memory import SessionMemory
from .state import AgentState


class AgentService:
    """应用层 Agent 服务。"""

    def __init__(self, llm, mcp_client, memory: SessionMemory | None = None):
        self.mcp_client = mcp_client
        self.memory = memory or SessionMemory()
        self.graph = build_agent_graph(llm, mcp_client.tools)

    async def run(self, session_id: str, user_input: str) -> str:
        """执行一轮对话，并把结果保存到对应 session。"""
        history = self.memory.get(session_id)

        # Agent 每次运行都拿到当前 session 的历史，因此可以多轮对话。
        state: AgentState = {
            "messages": [*history, HumanMessage(content=user_input)],
            "step": 0,
        }

        result = await self.graph.ainvoke(state)
        new_messages = result["messages"][len(history):]
        self.memory.append(session_id, new_messages)

        # Graph 最后一条消息就是最终回答。
        return result["messages"][-1].content
