"""Agent 对外服务层。

这一层把一次请求翻译成一次 Agent 执行。
HTTP 层不需要知道 LangGraph、MCP 或 Checkpoint 的细节。

本轮重点：
- 正常请求继续使用 run/run_stream。
- Agent 触发 interrupt 后，不保存“未完成”的最终状态。
- 用户确认后，通过 Command(resume=...) 恢复同一个 LangGraph thread。
"""

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages
from langgraph.types import Command

from .approval_errors import AgentApprovalRequired
from .approval_manager import ApprovalManager
from .approval_runtime import ApprovalRuntime
from .checkpoint import AgentCheckpoint
from .events import AgentEvent
from .graph import build_agent_graph
from .in_memory_checkpoint import InMemoryCheckpoint
from .limits import AgentLimits
from .observability import AgentRunTracker
from .state import AgentState
from .input_validation import validate_agent_input


class AgentService:
    """应用层 Agent 服务。"""

    def __init__(
        self,
        llm,
        mcp_client,
        checkpoint: AgentCheckpoint | None = None,
        limits: AgentLimits | None = None,
        tracker: AgentRunTracker | None = None,
        approval_manager: ApprovalManager | None = None,
    ):
        self.mcp_client = mcp_client
        self.checkpoint = checkpoint or InMemoryCheckpoint()
        self.limits = limits or AgentLimits()
        self.limits.validate()
        self.tracker = tracker or AgentRunTracker()
        self.approval_manager = approval_manager
        approval_runtime = (
            ApprovalRuntime(approval_manager) if approval_manager is not None else None
        )
        self.graph = build_agent_graph(
            llm,
            mcp_client.tools,
            self.limits,
            approval_runtime,
        )

    async def _build_state(self, session_id: str, user_input: str) -> AgentState:
        """从应用层 Checkpoint 恢复历史，再加入本轮用户消息。"""
        saved_state = await self.checkpoint.load(session_id)
        history = saved_state["messages"] if saved_state else []
        return {
            "messages": [*history, HumanMessage(content=user_input)],
            "step": 0,
        }

    @staticmethod
    def _interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
        """从 LangGraph 返回结果中取出 interrupt payload。"""
        interrupts = result.get("__interrupt__")
        if not interrupts:
            return None

        item = interrupts[0]
        value = getattr(item, "value", item)
        return value if isinstance(value, dict) else {"message": str(value)}

    async def run(self, session_id: str, user_input: str) -> str:
        """执行一轮 Agent；需要审批时抛出 AgentApprovalRequired。"""
        validate_agent_input(session_id, user_input)

        run = self.tracker.start(session_id)
        try:
            state = await self._build_state(session_id, user_input)
            config = {"configurable": {"thread_id": session_id}}
            result = await self.graph.ainvoke(state, config=config)

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

    async def resume(
        self,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> str:
        """恢复之前因人工审批而暂停的 LangGraph 执行。"""
        run = self.tracker.start(session_id)
        try:
            config = {"configurable": {"thread_id": session_id}}
            result = await self.graph.ainvoke(
                Command(
                    resume={
                        "approval_id": approval_id,
                        "approved": approved,
                        "reason": reason,
                    }
                ),
                config=config,
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

    async def run_stream(
        self,
        session_id: str,
        user_input: str,
    ) -> AsyncIterator[AgentEvent]:
        """流式执行 Agent；审批时发送 approval_required 后暂停。"""
        validate_agent_input(session_id, user_input)

        run = self.tracker.start(session_id)
        state = await self._build_state(session_id, user_input)
        final_state: AgentState = {
            "messages": list(state["messages"]),
            "step": state["step"],
        }
        config = {"configurable": {"thread_id": session_id}}

        try:
            async for update in self.graph.astream(
                state,
                config=config,
                stream_mode="updates",
            ):
                interrupt = update.get("__interrupt__")
                if interrupt:
                    item = interrupt[0]
                    payload = getattr(item, "value", item)
                    self.tracker.finish(run, "paused")
                    yield AgentEvent(
                        type="approval_required",
                        content=str(payload.get("message", "请确认是否继续。")),
                        approval_id=payload.get("approval_id"),
                        tool_name=payload.get("tool_name"),
                        data=payload,
                    )
                    return

                for node_name, node_state in update.items():
                    if node_name == "__interrupt__":
                        continue
                    messages = node_state.get("messages", [])
                    final_state["messages"] = add_messages(
                        final_state["messages"], messages
                    )
                    if "step" in node_state:
                        final_state["step"] = node_state["step"]

                    if node_name == "tools":
                        for message in messages:
                            yield AgentEvent(
                                type="tool_end",
                                content=str(getattr(message, "content", "")),
                                tool_name=getattr(message, "name", None),
                            )
                    elif node_name == "llm":
                        for message in messages:
                            content = getattr(message, "content", "")
                            tool_calls = getattr(message, "tool_calls", None)
                            if content and not tool_calls:
                                yield AgentEvent(type="answer", content=str(content))

            await self.checkpoint.save(session_id, final_state)
            self.tracker.finish(run, "success")
            yield AgentEvent(type="done")
        except Exception as exc:
            self.tracker.finish(run, "error", str(exc))
            yield AgentEvent(type="error", content="Agent execution failed")

    async def resume_stream(
        self,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """以流式方式恢复暂停的 Agent。"""
        run = self.tracker.start(session_id)
        config = {"configurable": {"thread_id": session_id}}
        try:
            async for update in self.graph.astream(
                Command(
                    resume={
                        "approval_id": approval_id,
                        "approved": approved,
                        "reason": reason,
                    }
                ),
                config=config,
                stream_mode="updates",
            ):
                interrupt = update.get("__interrupt__")
                if interrupt:
                    item = interrupt[0]
                    payload = getattr(item, "value", item)
                    yield AgentEvent(
                        type="approval_required",
                        content=str(payload.get("message", "请确认是否继续。")),
                        approval_id=payload.get("approval_id"),
                        tool_name=payload.get("tool_name"),
                        data=payload,
                    )
                    return

                for node_name, node_state in update.items():
                    messages = node_state.get("messages", [])
                    if node_name == "tools":
                        for message in messages:
                            yield AgentEvent(
                                type="tool_end",
                                content=str(getattr(message, "content", "")),
                                tool_name=getattr(message, "name", None),
                            )
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
