"""Agent Service：负责认证上下文、LangGraph 执行和对外流式事件。"""

from __future__ import annotations

from typing import Any, AsyncIterator

from langgraph.graph.message import add_messages
from langgraph.types import Command

from agent.events import AgentEvent
from agent.exceptions import AgentApprovalRequired
from agent.graph import AgentState
from auth.context import AuthContext, reset_auth_context, set_auth_context


class AgentService:
    """Agent 业务编排入口。"""

    # 其余实现保持当前版本不变；此文件本次只调整 run_stream 的事件映射。

    async def run_stream(self, session_id: str, user_input: str,
                         attachments: list[dict[str, Any]] | None = None,
                         authorization: str | None = None,
                         auth_context: AuthContext | None = None) -> AsyncIterator[AgentEvent]:
        """流式执行 Agent。

        注意：这里的流式事件是 Agent 内部事件，不直接绑定旧前端的 SSE 格式。
        API 层会根据不同入口把 AgentEvent 转换成对应的协议。
        """
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
                    final_state["messages"] = add_messages(final_state["messages"], messages)
                    for key in ("step", "business_facts", "attachments", "workflow_intent"):
                        if key in node_state:
                            final_state[key] = node_state[key]

                    if node_name == "tools":
                        for message in messages:
                            yield AgentEvent(
                                type="tool_end",
                                content=str(getattr(message, "content", "")),
                                tool_name=getattr(message, "name", None),
                            )
                    elif node_name == "llm":
                        for message in messages:
                            # LLM 发出 Tool Call 时，先产生 tool_start。
                            # 旧 /query 会在这里向前端发送“处理中”进度；
                            # 新 AgentEvent 保留结构化事件，由 API 层决定如何呈现。
                            for tool_call in getattr(message, "tool_calls", []) or []:
                                yield AgentEvent(
                                    type="tool_start",
                                    tool_name=tool_call.get("name"),
                                )

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
