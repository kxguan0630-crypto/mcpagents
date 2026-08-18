"""对外提供一个非常简单的 AgentService。

HTTP 层、CLI、测试代码都只需要调用 service.run()，
不需要知道 LangGraph 或 MCP 的内部细节。
"""

from langchain_core.messages import HumanMessage

from .graph import build_agent_graph
from .state import AgentState


class AgentService:
    def __init__(self, llm, mcp_client):
        self.mcp_client = mcp_client
        self.graph = build_agent_graph(llm, mcp_client.tools)

    async def run(self, user_input: str) -> str:
        """执行一次完整 Agent 任务。"""
        state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "step": 0,
        }
        result = await self.graph.ainvoke(state)
        return result["messages"][-1].content
