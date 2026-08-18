"""Agent 可观测性基础层。

这里先不引入复杂的 OpenTelemetry/LangSmith。
我们的目标是让源码非常容易理解：一次 Agent 请求对应一个 run_id，
并记录开始时间、结束时间、状态和错误信息。

以后如果需要接专业观测平台，只需要替换这个模块的实现，
AgentGraph 本身不需要知道具体平台。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


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

    def finish(self, status: str = "success", error: str | None = None) -> None:
        """结束本次 Agent Run，并记录最终状态。"""
        self.finished_at = time.monotonic()
        self.status = status
        self.error = error

    @property
    def duration_ms(self) -> int | None:
        """返回执行耗时；运行中则返回 None。"""
        if self.finished_at is None:
            return None
        return int((self.finished_at - self.started_at) * 1000)


class AgentRunTracker:
    """创建和结束 Agent Run。

    这是一个非常薄的抽象层：当前只打印日志。
    后续可以在这里增加 metrics、OpenTelemetry 或 LangSmith。
    """

    def start(self, session_id: str | None = None) -> AgentRun:
        run = AgentRun(session_id=session_id)
        print(f"[agent] run={run.run_id} status=started session={session_id}")
        return run

    def finish(self, run: AgentRun, status: str = "success", error: str | None = None) -> None:
        run.finish(status=status, error=error)
        print(
            f"[agent] run={run.run_id} status={run.status} "
            f"duration_ms={run.duration_ms} error={run.error}"
        )
