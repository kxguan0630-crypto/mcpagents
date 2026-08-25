"""Agent 对外服务层。

HTTP 只负责输入输出；AgentService 负责会话、LangGraph、Tool Runtime 和事件流。
工具是否展示给用户由 Tool metadata 决定，不再硬编码具体工具名称。
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
from .workflows.facts import build_workflow_fact_tools


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
        self._internal_tools = {
            tool.name: self._tool_metadata(tool)
            for tool in build_workflow_fact_tools()
        }

    @staticmethod
    def _tool_metadata(tool) -> dict[str, Any]:
        """读取 Tool 的稳定 metadata；没有 metadata 时按业务工具处理。"""
        metadata = getattr(tool, "metadata", None) or {}
        return {
            "visibility": metadata.get("visibility", "user"),
            "display_name": metadata.get("display_name") or tool.name,
            "category": metadata.get("category", "mcp_business"),
        }

    def _display_metadata(self, tool_name: str | None) -> dict[str, Any]:
        """从当前工具集合取得用户展示元数据。"""
        if not tool_name:
            return {"visibility": "user", "display_name": "业务工具", "category": "unknown"}
        if tool_name in self._internal_tools:
            return self._internal_tools[tool_name]
        for tool in self.mcp_client.tools:
            if tool.name == tool_name:
                return self._tool_metadata(tool)
        return {"visibility": "user", "display_name": tool_name, "category": "unknown"}

    async def _build_state(self, session_id: str, user_input: str, attachments: list[dict[str, Any]] | None = None) -> AgentState:
        """恢复历史并加入本轮输入；附件只保存引用，不保存二进制。"""
        saved_state = await self.checkpoint.load(session_id)
        history = saved_state.get("messages", []) if saved_state else []
        facts = saved_state.get("business_facts", {}) if saved_state else {}
        previous_attachments = saved_state.get("attachments", []) if saved_state else []
        return {
            "messages": [*history, _human_message(user_input, attachments or [])],
            "step": 0,
            "business_facts": facts,
            "attachments": attachments or previous_attachments,
            "workflow_intent": saved_state.get("workflow_intent", "general") if saved_state else "general",
        }

    @staticmethod
    def _interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
        interrupts = result.get("__interrupt__")
        if not interrupts:
            return None
        value = getattr(interrupts[0], "value", interrupts[0])
        return value if isinstance(value, dict) else {"message": str(value)}

    async def _resolve_auth(self, authorization: str | None, auth_context: AuthContext | None) -> AuthContext:
        if auth_context is not None:
            return auth_context
        if self.auth_verifier is None:
            raise RuntimeError("Agent authentication verifier is not configured")
        return await self.auth_verifier.verify(authorization)

    async def run(self, session_id: str, user_input: str, attachments: list[dict[str, Any]] | None = None,
                  authorization: str | None = None, auth_context: AuthContext | None = None) -> str:
        validate_agent_input(session_id, user_input)
        context = await self._resolve_auth(authorization, auth_context)
        token = set_auth_context(context)
        run = self.tracker.start(session_id)
        try:
            result = await self.graph.ainvoke(await self._build_state(session_id, user_input, attachments), config=self._config(session_id))
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
            reset_auth_context(token)

    async def resume(self, session_id: str, approval_id: str, approved: bool, reason: str | None = None,
                     authorization: str | None = None, auth_context: AuthContext | None = None) -> str:
        context = await self._resolve_auth(authorization, auth_context)
        token = set_auth_context(context)
        run = self.tracker.start(session_id)
        try:
            result = await self.graph.ainvoke(Command(resume={"approval_id": approval_id, "approved": approved, "reason": reason}), config=self._config(session_id))
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
            reset_auth_context(token)

    async def run_stream(self, session_id: str, user_input: str, attachments: list[dict[str, Any]] | None = None,
                         authorization: str | None = None, auth_context: AuthContext | None = None) -> AsyncIterator[AgentEvent]:
        """流式执行 Agent；只把 visibility=user 的 Tool 暴露给前端。"""
        validate_agent_input(session_id, user_input)
        context = await self._resolve_auth(authorization, auth_context)
        token = set_auth_context(context)
        run = self.tracker.start(session_id)
        state = await self._build_state(session_id, user_input, attachments)
        final_state: AgentState = dict(state)
        final_state["messages"] = list(state["messages"])
        try:
            async for update in self.graph.astream(state, config=self._config(session_id), stream_mode="updates"):
                interrupt = update.get("__interrupt__")
                if interrupt:
                    payload = getattr(interrupt[0], "value", interrupt[0])
                    self.tracker.finish(run, "paused")
                    yield AgentEvent(type="approval_required", content=str(payload.get("message", "请确认是否继续。")), approval_id=payload.get("approval_id"), tool_name=payload.get("tool_name"), data=payload)
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
                            tool_name = getattr(message, "name", None)
                            metadata = self._display_metadata(tool_name)
                            if metadata["visibility"] != "user":
                                continue
                            yield AgentEvent(type="tool_end", content=str(getattr(message, "content", "")), tool_name=tool_name, data=metadata)
                    elif node_name == "llm":
                        for message in messages:
                            for tool_call in getattr(message, "tool_calls", []) or []:
                                tool_name = tool_call.get("name")
                                metadata = self._display_metadata(tool_name)
                                if metadata["visibility"] != "user":
                                    continue
                                yield AgentEvent(type="tool_start", tool_name=tool_name, data=metadata)
                            content = getattr(message, "content", "")
                            if content and not getattr(message, "tool_calls", None):
                                yield AgentEvent(type="answer", content=str(content))
            await self.checkpoint.save(session_id, final_state)
            self.tracker.finish(run, "success")
            yield AgentEvent(type="done")
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            yield AgentEvent(type="error", content="Agent execution failed", data={"retryable": True})
        finally:
            reset_auth_context(token)

    async def resume_stream(self, session_id: str, approval_id: str, approved: bool, reason: str | None = None,
                            authorization: str | None = None, auth_context: AuthContext | None = None) -> AsyncIterator[AgentEvent]:
        """流式恢复暂停的 Agent。"""
        context = await self._resolve_auth(authorization, auth_context)
        token = set_auth_context(context)
        run = self.tracker.start(session_id)
        try:
            async for update in self.graph.astream(Command(resume={"approval_id": approval_id, "approved": approved, "reason": reason}), config=self._config(session_id), stream_mode="updates"):
                interrupt = update.get("__interrupt__")
                if interrupt:
                    payload = getattr(interrupt[0], "value", interrupt[0])
                    yield AgentEvent(type="approval_required", content=str(payload.get("message", "请确认。")), approval_id=payload.get("approval_id"), tool_name=payload.get("tool_name"), data=payload)
                    return
                for node_name, node_state in update.items():
                    messages = node_state.get("messages", [])
                    if node_name == "tools":
                        for message in messages:
                            tool_name = getattr(message, "name", None)
                            metadata = self._display_metadata(tool_name)
                            if metadata["visibility"] == "user":
                                yield AgentEvent(type="tool_end", content=str(getattr(message, "content", "")), tool_name=tool_name, data=metadata)
                    elif node_name == "llm":
                        for message in messages:
                            for tool_call in getattr(message, "tool_calls", []) or []:
                                tool_name = tool_call.get("name")
                                metadata = self._display_metadata(tool_name)
                                if metadata["visibility"] == "user":
                                    yield AgentEvent(type="tool_start", tool_name=tool_name, data=metadata)
                            content = getattr(message, "content", "")
                            if content and not getattr(message, "tool_calls", None):
                                yield AgentEvent(type="answer", content=str(content))
            state = await self.graph.aget_state(self._config(session_id))
            await self.checkpoint.save(session_id, state.values)
            if self.approval_manager is not None:
                await self.approval_manager.delete_request(approval_id)
            self.tracker.finish(run, "success")
            yield AgentEvent(type="done")
        except Exception:
            self.tracker.finish(run, "error", "resume failed")
            yield AgentEvent(type="error", content="Agent resume failed", data={"retryable": True})
        finally:
            reset_auth_context(token)

    @staticmethod
    def _config(session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}
