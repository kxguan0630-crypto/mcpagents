"""本地启动入口。

故意保持很短：真正的业务编排在 agent/ 中。
"""

import asyncio

from langchain_openai import ChatOpenAI

from agent.checkpoint_backend import create_graph_checkpointer
from agent.service import AgentService
from config import Settings
from mcp.client import MCPToolClient


async def main() -> None:
    settings = Settings.from_env()

    llm = ChatOpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model_name,
    )

    mcp = MCPToolClient(settings.mcp_config)
    await mcp.connect()

    # Checkpointer 在应用启动阶段创建一次，然后注入 AgentService。
    # AgentService / AgentGraph 不需要知道 Redis 的连接细节。
    graph_checkpointer = await create_graph_checkpointer(settings)

    try:
        agent = AgentService(
            llm,
            mcp,
            graph_checkpointer=graph_checkpointer,
        )
        print("Agent ready. 输入 quit 退出。")
        while True:
            text = input("You > ").strip()
            if text.lower() in {"quit", "exit"}:
                break
            print("Agent >", await agent.run("cli-session", text))
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(main())
