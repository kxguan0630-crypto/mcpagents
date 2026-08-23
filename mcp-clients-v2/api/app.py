"""HTTP 层。

职责保持很薄：HTTP -> Auth -> AgentService -> LangGraph -> MCP Tools。
/query 继续兼容原客户端的 text/session_id/image_list/authorization 参数，但真实的
认证边界统一在这里完成；认证失败不会进入 Agent Workflow。

注意：/query 的 SSE 协议必须保持与旧 mcp-clients/chatapi_case_mcp_client.py
完全一致。旧客户端读取的是：
    data: {"output": {"text": "...", "finish_reason": "...", "session_id": "..."}}
因此这里只做 AgentEvent -> 旧 SSE 协议的适配，不改变前端协议。
"""

import asyncio
import json

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

    def legacy_sse(session_id: str, text: str, finish_reason: str = "null") -> str:
        """生成旧 /query 使用的 SSE 包装格式。

        旧前端不是解析 AgentEvent，而是直接读取 response.body，把每个 SSE chunk
        的 output.text 当作增量文本。因此 /query 必须继续返回这一层 envelope。
        """
        payload = {
            "output": {
                "text": text,
                "finish_reason": finish_reason,
                "session_id": session_id,
            }
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> ChatResponse:
        """新版 Agent API：先验证 Token，再执行 Agent。"""
        return ChatResponse(session_id=request.session_id, answer=await run_request(request, authorization))

    @app.post("/query")
    async def query(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        """旧 /query 兼容入口：保留原客户端 SSE 协议。

        原 mcp-clients 的 process_query 会在最终回答阶段逐字符 yield，
        路由再把每个 chunk 包装成 output.text。新版 AgentService 的 answer
        事件是一条完整文本，因此这里按字符重新切成增量 SSE，保持前端行为一致。
        """
        context = await authenticate(authorization, request.authorization)

        async def event_generator():
            try:
                async for event in agent_service.run_stream(
                    request.session_id,
                    request.text,
                    attachments=request.input_attachments,
                    auth_context=context,
                ):
                    if event.type == "answer":
                        # 旧 process_query 是逐字符 yield；这里保持同样的增量粒度。
                        for char in event.content:
                            yield legacy_sse(request.session_id, char)
                            await asyncio.sleep(0)
                    elif event.type == "tool_start":
                        text = f"\n【处理中】{event.tool_name or '工具'}...\n\n"
                        yield legacy_sse(request.session_id, text)
                    elif event.type == "tool_end":
                        # 不把完整 Tool Result 原样暴露给前端；旧协议只需要一段进度文本。
                        text = f"\n【完成】{event.tool_name or '工具'}执行完成\n\n"
                        yield legacy_sse(request.session_id, text)
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

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-DashScope-SSE": "enable",
            },
        )

    @app.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> StreamingResponse:
        """新版 AgentEvent SSE；不改变新版协议。"""
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
