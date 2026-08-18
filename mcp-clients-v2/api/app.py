"""HTTP 层。

职责保持很薄：

    HTTP -> AgentService -> LangGraph -> MCP Tools

同时保留 /query 作为兼容入口，避免前端因为 Agent 重构而被迫修改请求路径。
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
        """把 HTTP 输入统一转换给 AgentService。"""
        attachments = request.attachments if request.attachments is not None else request.image_list
        return await agent_service.run(
            request.session_id,
            request.text,
            attachments=attachments or [],
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """新版 Agent API。支持文本和附件引用。"""
        answer = await run_request(request)
        return ChatResponse(session_id=request.session_id, answer=answer)

    @app.post("/query", response_model=ChatResponse)
    async def query(request: ChatRequest) -> ChatResponse:
        """兼容原客户端的 /query 入口。

        原客户端字段可以继续使用 query + image_list；内部已经转换成统一 AgentInput。
        """
        answer = await run_request(request)
        return ChatResponse(session_id=request.session_id, answer=answer)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        """把 AgentEvent 转成前端容易消费的 SSE。"""

        async def event_generator():
            attachments = request.attachments if request.attachments is not None else request.image_list
            async for event in agent_service.run_stream(
                request.session_id,
                request.text,
                attachments=attachments or [],
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
