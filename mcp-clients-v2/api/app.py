"""HTTP 层。

这里故意非常薄：

    HTTP -> AgentService -> AgentGraph -> MCP Tools

不要把 Agent 决策写进 FastAPI 路由，否则项目很快又会退化成大文件。
"""

from fastapi import FastAPI

from agent.service import AgentService
from .schemas import ChatRequest, ChatResponse


def create_app(agent_service: AgentService) -> FastAPI:
    """创建 FastAPI 应用，并注入已经初始化好的 AgentService。"""
    app = FastAPI(title="MCP Agent API", version="2.0")

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        # 路由只负责协议转换，真正的 Agent 工作交给 service。
        answer = await agent_service.run(request.session_id, request.message)
        return ChatResponse(session_id=request.session_id, answer=answer)

    return app
