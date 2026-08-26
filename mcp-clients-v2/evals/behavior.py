"""Agent 行为契约评估。

P11 不只检查最终文本，而检查 Required / Forbidden Tool、顺序和关键状态。
它可以直接消费运行期记录下来的 tool trace。
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BehaviorContract:
    name: str
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    required_order: tuple[str, ...] = ()
    required_facts: dict[str, Any] | None = None


@dataclass(frozen=True)
class BehaviorResult:
    contract: str
    passed: bool
    failures: tuple[str, ...] = ()


def evaluate_behavior(contract: BehaviorContract, tool_trace: list[str], facts: dict[str, Any] | None = None) -> BehaviorResult:
    failures: list[str] = []
    actual = list(tool_trace)

    for tool in contract.required_tools:
        if tool not in actual:
            failures.append(f"missing required tool: {tool}")

    for tool in contract.forbidden_tools:
        if tool in actual:
            failures.append(f"forbidden tool called: {tool}")

    cursor = 0
    for tool in contract.required_order:
        try:
            cursor = actual.index(tool, cursor) + 1
        except ValueError:
            failures.append(f"required order not satisfied at: {tool}")
            break

    actual_facts = facts or {}
    for key, expected in (contract.required_facts or {}).items():
        if actual_facts.get(key) != expected:
            failures.append(f"fact mismatch: {key}={actual_facts.get(key)!r}, expected {expected!r}")

    return BehaviorResult(contract.name, not failures, tuple(failures))
