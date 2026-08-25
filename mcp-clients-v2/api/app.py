"""HTTP 层。

HTTP 只负责协议转换。Agent Runtime 负责 Workflow、Tool、认证、恢复和事件。
/query 保持旧客户端 SSE envelope 不变，因此可以无感接入新版 Agent。
"""

import asyncio
import json

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent.approval_manager import ApprovalManager
from agent.service import AgentService
from auth.context import AuthContext
from auth.verifier import AuthVerifier, AuthenticationError
from .authenticated_approval_routes import create_authenticated_approval_router
from .schemas import ChatRequest, ChatResponse


def create_app(agent_service: AgentService, approval_manager: ApprovalManager | None = None,
               auth_verifier: AuthVerifier | None = None) -> FastAPI:
    """创建 FastAPI 应用。"""
    app = FastAPI(title="MCP Agent API", version="3.2")

    # 保持原项目 CORS 行为，前端可以直接从浏览器调用 /query。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "mcp-agent"}

    async def authenticate(header_authorization: str | None, body_authorization: str | None) -> AuthContext:
        """Header 优先，body authorization 作为旧客户端兼容入口。"""
        if auth_verifier is None:
            raise HTTPException(status_code=500, detail="Authentication is not configured")
        try:
            return await auth_verifier.verify(header_authorization or body_authorization)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    async def run_request(request: ChatRequest, header_authorization: str | None = None) -> str:
        context = await authenticate(header_authorization, request.authorization)
        return await agent_service.run(request.session_id, request.text, attachments=request.input_attachments, auth_context=context)

    def legacy_sse(session_id: str, text: str, finish_reason: str = "null") -> str:
        """保持旧 /query 的 output.text SSE 协议。"""
        payload = {"output": {"text": text, "finish_reason": finish_reason, "session_id": session_id}}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def display_name(event) -> str:
        """优先使用 Tool metadata 的人类可读名称，fallback 才显示工具名。"""
        return str((event.data or {}).get("display_name") or event.tool_name or "工具")

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, authorization: str | None = Header(default=None)) -> ChatResponse:
        return ChatResponse(session_id=request.session_id, answer=await run_request(request, authorization))

    @app.post("/query")
    async def query(request: ChatRequest, authorization: str | None = Header(default=None)) -> StreamingResponse:
        """旧客户端兼容 SSE；内部 Workflow Tool 不会进入这里。"""
        context = await authenticate(authorization, request.authorization)

        async def event_generator():
            try:
                async for event in agent_service.run_stream(request.session_id, request.text,
                                                            attachments=request.input_attachments,
                                                            auth_context=context):
                    if event.type == "answer":
                        for char in event.content:
                            yield legacy_sse(request.session_id, char)
                            await asyncio.sleep(0)
                    elif event.type == "tool_start":
                        yield legacy_sse(request.session_id, f"\n【处理中】{display_name(event)}…\n\n")
                    elif event.type == "tool_end":
                        yield legacy_sse(request.session_id, f"\n【完成】{display_name(event)}\n\n")
                    elif event.type == "approval_required":
                        yield legacy_sse(request.session_id, event.content)
                    elif event.type == "error":
                        yield legacy_sse(request.session_id, event.content or "系统异常，请稍后再试", "error")
                    elif event.type == "done":
                        yield legacy_sse(request.session_id, "", "stop")
            except asyncio.CancelledError:
                yield legacy_sse(request.session_id, "Task was cancelled", "cancelled")
                raise
            except Exception as exc:
                yield legacy_sse(request.session_id, f"Unexpected error: {exc}", "error")

        return StreamingResponse(event_generator(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-DashScope-SSE": "enable"})

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest, authorization: str | None = Header(default=None)) -> StreamingResponse:
        context = await authenticate(authorization, request.authorization)

        async def event_generator():
            async for event in agent_service.run_stream(request.session_id, request.text,
                                                        attachments=request.input_attachments,
                                                        auth_context=context):
                yield event.to_sse()

        return StreamingResponse(event_generator(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    if approval_manager is not None:
        if auth_verifier is None:
            raise RuntimeError("Authentication is required for approval routes")
        app.include_router(create_authenticated_approval_router(approval_manager, agent_service, auth_verifier))
    return app
