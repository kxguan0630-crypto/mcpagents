"""Workflow 注册中心。

这里集中维护“意图 → Workflow”的关系。
Graph 不再写 if intent == ...；新增业务流程时只需注册新的 Workflow。
"""

from __future__ import annotations

from .base import Workflow


class WorkflowRegistry:
    """可扩展的 Workflow 注册表。"""

    def __init__(self, workflows: list[Workflow] | None = None):
        self._workflows: dict[str, Workflow] = {}
        for workflow in workflows or []:
            self.register(workflow)

    def register(self, workflow: Workflow) -> None:
        """注册一个 Workflow；重复意图直接报错，避免配置悄悄覆盖。"""
        if workflow.intent in self._workflows:
            raise ValueError(f"Workflow intent already registered: {workflow.intent}")
        self._workflows[workflow.intent] = workflow

    def resolve(self, intent: str | None) -> Workflow | None:
        """根据意图取得 Workflow；未知意图返回 None。"""
        if not intent:
            return None
        return self._workflows.get(intent)

    def all(self) -> tuple[Workflow, ...]:
        """返回当前注册的 Workflow，便于测试和观测。"""
        return tuple(self._workflows.values())
