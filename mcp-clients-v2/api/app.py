"""HTTP 层。

职责保持很薄：HTTP -> AgentService -> LangGraph -> MCP Tools。
同时保留 /query 作为原客户端兼容入口，并保持原有 authorization/image_list 参数。

Authorization 优先从 HTTP Header 读取，这样前端可以继续按原有鉴权方式发送 Token，
而不是要求用户在 CLI 中手工输入 Token。
"""

from fastapi import FastAPI, Header
from fastapi.responses import StreamingResponse

from agent.approval_manager import ApprovalManager
from agent.service import AgentService
from .approval_routes import create_approval_router
from .schemas import ChatRequest, ChatResponse


def create_app(agent_service: AgentService, approval_manager: ApprovalManager | None = None) -> FastAPI:
    """创建 FastAPI 应用，并注入已经初始化好的 AgentService。"""
    app = FastAPI(title="MCP Agent API", version="3.0")

    @app.get("/")
    async def health() -> dict[str, str]:
        """最小健康检查；浏览器访问 http://localhost:5000/ 时可以直接确认服务已启动。"""
        return {"status": "ok", "service": "mcp-agent"}

    async def run_request(request: ChatRequest, header_authorization: str | None = None) -> str:
        """把 HTTP 输入统一交给 AgentService。

        Header 优先，body authorization 作为兼容兜底。
        """
        authorization = header_authorization or request.authorization
        return await agent_service.run(
            request.session_id,
            request.text,
            attachments=request.input_attachments,
            authorization=authorization,
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> ChatResponse:
        """新版 Agent API：支持文本、附件和 Authorization Header。"""
        return ChatResponse(session_id=request.session_id, answer=await run_request(request, authorization))

    @app.post("/query", response_model=ChatResponse)
    async def query(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> ChatResponse:
        """原客户端兼容入口：query + image_list + Authorization Header。"""
        return ChatResponse(session_id=request.session_id, answer=await run_request(request, authorization))

    @app.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        """把 AgentEvent 转成前端容易消费的 SSE。"""
        effective_authorization = authorization or request.authorization

        async def event_generator():
            async for event in agent_service.run_stream(
                request.session_id,
                request.text,
                attachments=request.input_attachments,
                authorization=effective_authorization,
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
