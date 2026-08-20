"""本地启动入口。

支持两种模式：
1. ``--mode cli``：本地流程调试，Token 通过 ``--token`` 或 ``AGENT_AUTHORIZATION`` 提供；
2. ``--mode api``：启动 HTTP API，前端通过 Authorization Header 调用 /query。

HTTP/CLI 共用同一个 AuthVerifier，不绕过认证。
"""

from __future__ import annotations

import argparse
import asyncio
import os

import uvicorn
from langchain_openai import ChatOpenAI

from agent.checkpoint_backend import create_graph_checkpointer
from agent.service import AgentService
from api.app import create_app
from auth.verifier import AuthVerifier
from config import Settings
from mcp_intergration.client import MCPToolClient


def parse_args() -> argparse.Namespace:
    """解析启动参数。默认保持 CLI，避免影响已有本地调试习惯。"""
    parser = argparse.ArgumentParser(description="MCP Agent Client")
    parser.add_argument("--mode", choices=("cli", "api"), default="cli", help="启动 CLI 或 HTTP API")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 监听地址")
    parser.add_argument("--port", type=int, default=5000, help="HTTP 监听端口")
    parser.add_argument("--token", default=None, help="CLI 调试用 Authorization 值，例如 'Bearer xxx'")
    return parser.parse_args()


async def build_agent() -> tuple[AgentService, MCPToolClient, AuthVerifier | None]:
    """初始化 LLM、MCP Client、Checkpoint、认证器和 AgentService。"""
    settings = Settings.from_env()

    llm = ChatOpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model_name,
    )

    mcp = MCPToolClient(settings.mcp_config)
    await mcp.connect()
    graph_checkpointer = await create_graph_checkpointer(settings)

    auth_verifier = AuthVerifier(settings.csn_url, settings.auth_timeout_seconds) if settings.csn_url else None
    agent = AgentService(
        llm,
        mcp,
        graph_checkpointer=graph_checkpointer,
        auth_verifier=auth_verifier,
    )
    return agent, mcp, auth_verifier


async def run_cli(agent: AgentService, token: str | None) -> None:
    """CLI 调试入口；必须提供经过 CSN 验证的 Authorization Token。"""
    if not token:
        raise RuntimeError("CLI requires --token or AGENT_AUTHORIZATION")
    print("Agent ready. 输入 quit 退出。")
    while True:
        text = input("You > ").strip()
        if text.lower() in {"quit", "exit"}:
            return
        print("Agent >", await agent.run("cli-session", text, authorization=token))


async def run_api(agent: AgentService, auth_verifier: AuthVerifier, host: str, port: int) -> None:
    """启动 HTTP API。"""
    app = create_app(agent, auth_verifier=auth_verifier)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    args = parse_args()
    agent, mcp, auth_verifier = await build_agent()
    try:
        if args.mode == "api":
            if auth_verifier is None:
                raise RuntimeError("CSN_URL must be configured for API mode")
            print(f"Agent API ready: http://{args.host}:{args.port}")
            print(f"POST http://{args.host}:{args.port}/query")
            await run_api(agent, auth_verifier, args.host, args.port)
        else:
            token = args.token or os.getenv("AGENT_AUTHORIZATION")
            await run_cli(agent, token)
    finally:
        await mcp.close()


if __name__ == "__main__":
    asyncio.run(main())
