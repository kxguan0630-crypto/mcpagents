"""HTTP 层。

职责保持很薄：HTTP -> Auth -> AgentService -> LangGraph -> MCP Tools。
/query 继续兼容原客户端的 text/session_id/image_list/authorization 参数，但真实的
认证边界统一在这里完成；认证失败不会进入 Agent Workflow。
"""

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from agent.approval_manager import ApprovalManager
from agent.service import AgentService
from auth.context import AuthContext
from auth.verifier import AuthVerifier, AuthenticationError
from .authenticated_approval_routes import create_authenticated_approval_router
from .schemas import ChatRequest, ChatResponse


def create_app(
    agent_service: AgentService,
    approval_manager: ApprovalManager | None = None,
    auth_verifier: AuthVerifier | None = None,
) -> FastAPI:
    """创建 FastAPI 应用，并注入已经初始化好的 AgentService/AuthVerifier。"""
    app = FastAPI(title="MCP Agent API", version="3.1")

    @app.get("/")
    async def health() -> dict[str, str]:
        """最小健康检查；不需要业务 JWT，便于容器探活。"""
        return {"status": "ok", "service": "mcp-agent"}

    async def authenticate(header_authorization: str | None, body_authorization: str | None) -> AuthContext:
        """Header 优先，body authorization 只作为旧客户端兼容兜底。"""
        if auth_verifier is None:
            raise HTTPException(status_code=500, detail="Authentication is not configured")
        authorization = header_authorization or body_authorization
        try:
            return await auth_verifier.verify(authorization)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    async def run_request(request: ChatRequest, header_authorization: str | None = None) -> str:
        """认证成功后，把 AuthContext 交给 AgentService。"""
        context = await authenticate(header_authorization, request.authorization)
        return await agent_service.run(
            request.session_id,
            request.text,
            attachments=request.input_attachments,
            auth_context=context,
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> ChatResponse:
        """新版 Agent API：先验证 Token，再执行 Agent。"""
        return ChatResponse(session_id=request.session_id, answer=await run_request(request, authorization))

    @app.post("/query", response_model=ChatResponse)
    async def query(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> ChatResponse:
        """原客户端兼容入口：认证方式恢复为原来的 Authorization -> CSN 校验。"""
        return ChatResponse(session_id=request.session_id, answer=await run_request(request, authorization))

    @app.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        """把认证后的 AgentEvent 转成前端容易消费的 SSE。"""
        context = await authenticate(authorization, request.authorization)

        async def event_generator():
            async for event in agent_service.run_stream(
                request.session_id,
                request.text,
                attachments=request.input_attachments,
                auth_context=context,
            ):
                yield event.to_sse()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    if approval_manager is not None:
        if auth_verifier is None:
            raise RuntimeError("Authentication is required for approval routes")
        app.include_router(create_authenticated_approval_router(approval_manager, agent_service, auth_verifier))
    return app
