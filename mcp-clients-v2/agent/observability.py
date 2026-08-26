"""Agent 可观测性基础层。

P10 目标：一次 Agent Run 不只记录总耗时，还记录阶段、Tool、错误和重试。
实现保持轻量，不强绑定 OpenTelemetry/LangSmith；以后可以替换 Sink。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentTraceEvent:
    """一次运行期事件。"""

    event: str
    timestamp: float = field(default_factory=time.time)
    tool_name: str | None = None
    duration_ms: int | None = None
    status: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRun:
    """描述一次完整 Agent 执行。"""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    session_id: str | None = None
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    status: str = "running"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    events: list[AgentTraceEvent] = field(default_factory=list)

    def add_event(self, event: str, **kwargs: Any) -> AgentTraceEvent:
        item = AgentTraceEvent(event=event, **kwargs)
        self.events.append(item)
        return item

    def finish(self, status: str = "success", error: str | None = None) -> None:
        self.finished_at = time.monotonic()
        self.status = status
        self.error = error
        self.add_event("run_end", status=status, error=error)

    @property
    def duration_ms(self) -> int | None:
        if self.finished_at is None:
            return None
        return int((self.finished_at - self.started_at) * 1000)

    def snapshot(self) -> dict[str, Any]:
        """返回脱离运行时对象的可序列化 Trace。"""
        data = asdict(self)
        data["duration_ms"] = self.duration_ms
        return data


class AgentRunTracker:
    """Run 生命周期和结构化事件追踪。

    默认仍输出简洁日志，避免引入额外基础设施；调用方可以读取 run.snapshot()
    或通过后续 Sink 接入日志/指标/Trace 平台。
    """

    def start(self, session_id: str | None = None, metadata: dict[str, Any] | None = None) -> AgentRun:
        run = AgentRun(session_id=session_id, metadata=dict(metadata or {}))
        run.add_event("run_start", metadata=run.metadata)
        print(f"[agent] run={run.run_id} status=started session={session_id}")
        return run

    def record(self, run: AgentRun, event: str, **kwargs: Any) -> None:
        run.add_event(event, **kwargs)
        tool = f" tool={kwargs['tool_name']}" if kwargs.get("tool_name") else ""
        print(f"[agent] run={run.run_id} event={event}{tool}")

    def finish(self, run: AgentRun, status: str = "success", error: str | None = None) -> None:
        run.finish(status=status, error=error)
        print(
            f"[agent] run={run.run_id} status={run.status} "
            f"duration_ms={run.duration_ms} error={run.error}"
        )
