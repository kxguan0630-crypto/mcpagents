"""HTTP 层。

职责保持很薄：HTTP -> AgentService -> LangGraph -> MCP Tools。
同时保留 /query 作为原客户端兼容入口。
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from agent.approval_manager import ApprovalManager
from agent.service import AgentService
from .approval_routes import create_approval_router
from .schemas import ChatRequest, ChatResponse


def create_app(
    agent_service: AgentService,
    approval_manager: ApprovalManager | None = None,
) -> FastAPI:
    """创建 FastAPI 应用，并注入已经初始化好的 AgentService。"""
    app = FastAPI(title="MCP Agent API", version="3.0")

    async def run_request(request: ChatRequest) -> str:
        """把 HTTP 输入统一交给 AgentService。"""
        return await agent_service.run(
            request.session_id,
            request.text,
            attachments=request.input_attachments,
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """新版 Agent API：支持文本和附件引用。"""
        answer = await run_request(request)
        return ChatResponse(session_id=request.session_id, answer=answer)

    @app.post("/query", response_model=ChatResponse)
    async def query(request: ChatRequest) -> ChatResponse:
        """原客户端兼容入口：query + image_list 会自动转换。"""
        answer = await run_request(request)
        return ChatResponse(session_id=request.session_id, answer=answer)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        """把 AgentEvent 转成前端容易消费的 SSE。"""

        async def event_generator():
            async for event in agent_service.run_stream(
                request.session_id,
                request.text,
                attachments=request.input_attachments,
            ):
                yield event.to_sse()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    if approval_manager is not None:
        app.include_router(create_approval_router(approval_manager, agent_service))

    return app
