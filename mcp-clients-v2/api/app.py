"""HTTP 层。

这里故意非常薄：

    HTTP -> AgentService -> AgentGraph -> MCP Tools

不要把 Agent 决策写进 FastAPI 路由，否则项目很快又会退化成大文件。

本轮增加 /chat/stream：
- /chat：普通 JSON 响应。
- /chat/stream：Server-Sent Events 流式响应。
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from agent.service import AgentService
from .schemas import ChatRequest, ChatResponse


def create_app(agent_service: AgentService) -> FastAPI:
    """创建 FastAPI 应用，并注入已经初始化好的 AgentService。"""
    app = FastAPI(title="MCP Agent API", version="2.1")

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        # 路由只负责协议转换，真正的 Agent 工作交给 service。
        answer = await agent_service.run(request.session_id, request.message)
        return ChatResponse(session_id=request.session_id, answer=answer)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        """把 AgentEvent 转成浏览器/前端容易消费的 SSE。"""

        async def event_generator():
            async for event in agent_service.run_stream(
                request.session_id,
                request.message,
            ):
                yield event.to_sse()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app
