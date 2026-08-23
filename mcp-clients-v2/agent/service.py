"""Agent 对外服务层。

HTTP 只负责输入输出；AgentService 负责会话、LangGraph 和 MCP Tool 运行时上下文。
认证信息通过 AuthContext 进入当前异步运行上下文，不写入 business_facts，也不写入消息。
"""

from collections.abc import AsyncIterator
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.message import add_messages
from langgraph.types import Command

from auth.context import AuthContext, reset_auth_context, set_auth_context
from auth.verifier import AuthVerifier
from .approval_errors import AgentApprovalRequired
from .approval_manager import ApprovalManager
from .approval_runtime import ApprovalRuntime
from .checkpoint import AgentCheckpoint
from .events import AgentEvent
from .graph import build_agent_graph, _human_message
from .in_memory_checkpoint import InMemoryCheckpoint
from .limits import AgentLimits
from .observability import AgentRunTracker
from .state import AgentState
from .input_validation import validate_agent_input


class AgentService:
    """应用层 Agent 服务。"""

    def __init__(self, llm, mcp_client, checkpoint: AgentCheckpoint | None = None,
                 limits: AgentLimits | None = None, tracker: AgentRunTracker | None = None,
                 approval_manager: ApprovalManager | None = None,
                 graph_checkpointer: BaseCheckpointSaver | None = None,
                 auth_verifier: AuthVerifier | None = None):
        self.mcp_client = mcp_client
        self.auth_verifier = auth_verifier
        self.checkpoint = checkpoint or InMemoryCheckpoint()
        self.limits = limits or AgentLimits()
        self.limits.validate()
        self.tracker = tracker or AgentRunTracker()
        self.approval_manager = approval_manager
        approval_runtime = ApprovalRuntime(approval_manager) if approval_manager is not None else None
        self.graph = build_agent_graph(llm, mcp_client.tools, self.limits, approval_runtime, checkpointer=graph_checkpointer)

    async def _build_state(self, session_id: str, user_input: str,
                           attachments: list[dict[str, Any]] | None = None) -> AgentState:
        """恢复历史并加入本轮输入；附件只保存引用，不保存二进制。"""
        saved_state = await self.checkpoint.load(session_id)
        history = saved_state.get("messages", []) if saved_state else []
        facts = saved_state.get("business_facts", {}) if saved_state else {}
        previous_attachments = saved_state.get("attachments", []) if saved_state else []
        current_attachments = attachments or []
        return {
            "messages": [*history, _human_message(user_input, current_attachments)],
            "step": 0,
            "business_facts": facts,
            "attachments": current_attachments or previous_attachments,
            "workflow_intent": saved_state.get("workflow_intent", "general") if saved_state else "general",
        }

    @staticmethod
    def _interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
        """从 LangGraph 结果中读取 interrupt payload。"""
        interrupts = result.get("__interrupt__")
        if not interrupts:
            return None
        item = interrupts[0]
        value = getattr(item, "value", item)
        return value if isinstance(value, dict) else {"message": str(value)}

    async def _resolve_auth(self, authorization: str | None, auth_context: AuthContext | None) -> AuthContext:
        """统一获得已验证身份；没有上下文时通过 CSN 验证原始 Token。"""
        if auth_context is not None:
            return auth_context
        if self.auth_verifier is None:
            raise RuntimeError("Agent authentication verifier is not configured")
        return await self.auth_verifier.verify(authorization)

    async def run(self, session_id: str, user_input: str,
                  attachments: list[dict[str, Any]] | None = None,
                  authorization: str | None = None,
                  auth_context: AuthContext | None = None) -> str:
        """执行一轮 Agent；认证必须先通过，再进入 LangGraph。"""
        validate_agent_input(session_id, user_input)
        context = await self._resolve_auth(authorization, auth_context)
        auth_token = set_auth_context(context)
        run = self.tracker.start(session_id)
        try:
            state = await self._build_state(session_id, user_input, attachments)
            result = await self.graph.ainvoke(state, config=self._config(session_id))
            approval = self._interrupt_payload(result)
            if approval is not None:
                self.tracker.finish(run, "paused")
                raise AgentApprovalRequired(approval)
            await self.checkpoint.save(session_id, result)
            self.tracker.finish(run, "success")
            return result["messages"][-1].content
        except AgentApprovalRequired:
            raise
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            raise
        finally:
            reset_auth_context(auth_token)

    async def resume(self, session_id: str, approval_id: str, approved: bool,
                     reason: str | None = None, authorization: str | None = None,
                     auth_context: AuthContext | None = None) -> str:
        """恢复暂停的 Agent；恢复执行同样必须绑定已验证身份。"""
        context = await self._resolve_auth(authorization, auth_context)
        auth_token = set_auth_context(context)
        run = self.tracker.start(session_id)
        try:
            result = await self.graph.ainvoke(
                Command(resume={"approval_id": approval_id, "approved": approved, "reason": reason}),
                config=self._config(session_id),
            )
            approval = self._interrupt_payload(result)
            if approval is not None:
                raise AgentApprovalRequired(approval)
            await self.checkpoint.save(session_id, result)
            if self.approval_manager is not None:
                await self.approval_manager.delete_request(approval_id)
            self.tracker.finish(run, "success")
            return result["messages"][-1].content
        except AgentApprovalRequired:
            self.tracker.finish(run, "paused")
            raise
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            raise
        finally:
            reset_auth_context(auth_token)

    async def run_stream(self, session_id: str, user_input: str,
                         attachments: list[dict[str, Any]] | None = None,
                         authorization: str | None = None,
                         auth_context: AuthContext | None = None) -> AsyncIterator[AgentEvent]:
        """流式执行 Agent；认证上下文覆盖整个 Graph 流式执行生命周期。"""
        validate_agent_input(session_id, user_input)
        context = await self._resolve_auth(authorization, auth_context)
        auth_token = set_auth_context(context)
        run = self.tracker.start(session_id)
        state = await self._build_state(session_id, user_input, attachments)
        final_state: AgentState = dict(state)
        final_state["messages"] = list(state["messages"])
        try:
            async for update in self.graph.astream(state, config=self._config(session_id), stream_mode="updates"):
                interrupt = update.get("__interrupt__")
                if interrupt:
                    item = interrupt[0]
                    payload = getattr(item, "value", item)
                    self.tracker.finish(run, "paused")
                    yield AgentEvent(type="approval_required", content=str(payload.get("message", "请确认是否继续。")),
                                     approval_id=payload.get("approval_id"), tool_name=payload.get("tool_name"), data=payload)
                    return
                for node_name, node_state in update.items():
                    if node_name == "__interrupt__":
                        continue
                    messages = node_state.get("messages", [])
                    final_state["messages"] = add_messages(final_state["messages"], messages)
                    for key in ("step", "business_facts", "attachments", "workflow_intent"):
                        if key in node_state:
                            final_state[key] = node_state[key]
                    if node_name == "tools":
                        for message in messages:
                            yield AgentEvent(type="tool_end", content=str(getattr(message, "content", "")), tool_name=getattr(message, "name", None))
                    elif node_name == "llm":
                        for message in messages:
                            # 兼容旧 /query 的“处理中”提示：工具调用发生时先发 tool_start。
                            for tool_call in getattr(message, "tool_calls", []) or []:
                                yield AgentEvent(type="tool_start", tool_name=tool_call.get("name"))
                            content = getattr(message, "content", "")
                            if content and not getattr(message, "tool_calls", None):
                                yield AgentEvent(type="answer", content=str(content))
            await self.checkpoint.save(session_id, final_state)
            self.tracker.finish(run, "success")
            yield AgentEvent(type="done")
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            yield AgentEvent(type="error", content="Agent execution failed")
        finally:
            reset_auth_context(auth_token)

    async def resume_stream(self, session_id: str, approval_id: str, approved: bool,
                            reason: str | None = None, authorization: str | None = None,
                            auth_context: AuthContext | None = None) -> AsyncIterator[AgentEvent]:
        """流式恢复暂停的 Agent。"""
        context = await self._resolve_auth(authorization, auth_context)
        auth_token = set_auth_context(context)
        run = self.tracker.start(session_id)
        config = self._config(session_id)
        try:
            async for update in self.graph.astream(
                Command(resume={"approval_id": approval_id, "approved": approved, "reason": reason}),
                config=config, stream_mode="updates",
            ):
                interrupt = update.get("__interrupt__")
                if interrupt:
                    item = interrupt[0]
                    payload = getattr(item, "value", item)
                    yield AgentEvent(type="approval_required", content=str(payload.get("message", "请确认是否继续。")),
                                     approval_id=payload.get("approval_id"), tool_name=payload.get("tool_name"), data=payload)
                    return
                for node_name, node_state in update.items():
                    messages = node_state.get("messages", [])
                    if node_name == "tools":
                        for message in messages:
                            yield AgentEvent(type="tool_end", content=str(getattr(message, "content", "")), tool_name=getattr(message, "name", None))
                    elif node_name == "llm":
                        for message in messages:
                            content = getattr(message, "content", "")
                            if content and not getattr(message, "tool_calls", None):
                                yield AgentEvent(type="answer", content=str(content))
            state = await self.graph.aget_state(config)
            await self.checkpoint.save(session_id, state.values)
            if self.approval_manager is not None:
                await self.approval_manager.delete_request(approval_id)
            self.tracker.finish(run, "success")
            yield AgentEvent(type="done")
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            yield AgentEvent(type="error", content="Agent resume failed")
        finally:
            reset_auth_context(auth_token)

    @staticmethod
    def _config(session_id: str) -> dict[str, Any]:
        """只保留 LangGraph 自身需要的配置；认证不进入 Graph config。"""
        return {"configurable": {"thread_id": session_id}}
