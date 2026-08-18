"""HTTP 层。

这里故意保持非常薄：

    HTTP -> AgentService -> AgentGraph -> MCP Tools

审批接口也遵循同一个原则：HTTP 只接收用户决定，真正的 Agent resume
由 AgentService 完成。
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
    """创建 FastAPI 应用，并注入已经初始化好的服务。"""
    app = FastAPI(title="MCP Agent API", version="2.2")

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """执行一次普通 Agent 请求。"""
        answer = await agent_service.run(request.session_id, request.message)
        return ChatResponse(session_id=request.session_id, answer=answer)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        """把 AgentEvent 转成前端容易消费的 SSE。"""

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

    # 审批服务是可选的：不传就不会注册审批接口。
    # 这样普通 Agent 仍然可以单独运行，学习成本最低。
    if approval_manager is not None:
        app.include_router(create_approval_router(approval_manager, agent_service))

    return app
