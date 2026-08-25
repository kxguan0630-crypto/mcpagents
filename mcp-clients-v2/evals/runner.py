"""离线 Agent 行为评估器。

输入是一组已经发生的 Tool 名称和最终回答，不需要启动 LLM。
真实运行时可以把 AgentEvent/tool trace 转换成同样的输入，再执行这些契约。
"""

from dataclasses import dataclass

from .cases import CASES, EvalCase


@dataclass(frozen=True)
class EvalResult:
    case: str
    passed: bool
    failures: tuple[str, ...] = ()


def evaluate(case: EvalCase, tool_sequence: list[str], answer: str = "") -> EvalResult:
    failures: list[str] = []
    actual = list(tool_sequence)
    expected = list(case.tool_sequence)

    # expected 必须按顺序出现，但允许中间存在额外的非关键工具。
    cursor = 0
    for expected_tool in expected:
        try:
            cursor = actual.index(expected_tool, cursor) + 1
        except ValueError:
            failures.append(f"missing required tool: {expected_tool}")
            break

    for forbidden in case.forbidden_tools:
        if forbidden in actual:
            failures.append(f"forbidden tool called: {forbidden}")

    for text in case.answer_contains:
        if text not in answer:
            failures.append(f"answer missing: {text}")

    return EvalResult(case=case.name, passed=not failures, failures=tuple(failures))


def run_smoke_evals() -> list[EvalResult]:
    """执行一组最小离线回归；这里使用符合契约的 trace 验证评估器本身。"""
    traces = {
        CASES[0].name: ["get_patients_by_name_and_phone"],
        CASES[1].name: ["get_patients_by_name_and_phone", "case_add"],
        CASES[2].name: ["get_product_list", "record_design_decision"],
        CASES[3].name: ["image_process"],
    }
    return [evaluate(case, traces[case.name]) for case in CASES]


def main() -> int:
    results = run_smoke_evals()
    for result in results:
        if result.passed:
            print(f"PASS {result.case}")
        else:
            print(f"FAIL {result.case}: {'; '.join(result.failures)}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
