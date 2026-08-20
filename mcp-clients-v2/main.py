"""本地启动入口。

支持两种模式：
1. ``--mode cli``：保留原来的命令行调试方式；
2. ``--mode api``：启动 HTTP API，前端通过 ``http://localhost:5000/query`` 调用。

Authorization 不再依赖命令行输入：HTTP 模式直接从请求头 ``Authorization`` 或请求体
``authorization`` 传入，并由 AgentService 放入本次 Graph Runtime config。
"""

from __future__ import annotations

import argparse
import asyncio

import uvicorn
from langchain_openai import ChatOpenAI

from agent.checkpoint_backend import create_graph_checkpointer
from agent.service import AgentService
from api.app import create_app
from config import Settings
from mcp_intergration.client import MCPToolClient


def parse_args() -> argparse.Namespace:
    """解析启动参数。默认保持 CLI，避免影响已有本地调试习惯。"""
    parser = argparse.ArgumentParser(description="MCP Agent Client")
    parser.add_argument("--mode", choices=("cli", "api"), default="cli", help="启动 CLI 或 HTTP API")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 监听地址")
    parser.add_argument("--port", type=int, default=5000, help="HTTP 监听端口")
    return parser.parse_args()


async def build_agent() -> tuple[AgentService, MCPToolClient]:
    """初始化 LLM、MCP Client、Checkpoint 和 AgentService。"""
    settings = Settings.from_env()

    llm = ChatOpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model_name,
    )

    mcp = MCPToolClient(settings.mcp_config)
    await mcp.connect()
    graph_checkpointer = await create_graph_checkpointer(settings)

    agent = AgentService(
        llm,
        mcp,
        graph_checkpointer=graph_checkpointer,
    )
    return agent, mcp


async def run_cli(agent: AgentService) -> None:
    """保留原 CLI 调试入口；CLI 适合本地流程调试。"""
    print("Agent ready. 输入 quit 退出。")
    while True:
        text = input("You > ").strip()
        if text.lower() in {"quit", "exit"}:
            return
        print("Agent >", await agent.run("cli-session", text))


async def run_api(agent: AgentService, host: str, port: int) -> None:
    """启动 HTTP API。"""
    app = create_app(agent)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    args = parse_args()
    agent, mcp = await build_agent()
    try:
        if args.mode == "api":
            print(f"Agent API ready: http://{args.host}:{args.port}")
            print(f"POST http://{args.host}:{args.port}/query")
            await run_api(agent, args.host, args.port)
        else:
            await run_cli(agent)
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(main())
