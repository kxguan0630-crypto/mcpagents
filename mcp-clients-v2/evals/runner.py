"""离线 Agent 行为评估器。

输入是一组已经发生的 Tool 名称和最终回答，不需要启动 LLM。
真实运行时可以把 AgentEvent/tool trace 转换成同样的输入，再执行这些契约。
"""

from dataclasses import dataclass

from .behavior import BehaviorContract, evaluate_behavior
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


def run_behavior_contract_smoke() -> list[EvalResult]:
    """用行为契约覆盖核心业务规则。"""
    contracts = (
        BehaviorContract(
            name="case_creation_guard",
            required_tools=("get_patients_by_name_and_phone",),
            forbidden_tools=("case_add",),
        ),
        BehaviorContract(
            name="new_patient_case_creation",
            required_order=("get_patients_by_name_and_phone", "case_add"),
        ),
        BehaviorContract(
            name="design_skips_prescription",
            required_tools=("get_product_list", "record_design_decision"),
            forbidden_tools=("record_order_decisions.recipe_decision",),
        ),
        BehaviorContract(
            name="post_order_image_update",
            required_tools=("image_process",),
        ),
    )
    traces = (
        ["get_patients_by_name_and_phone"],
        ["get_patients_by_name_and_phone", "case_add"],
        ["get_product_list", "record_design_decision"],
        ["image_process"],
    )
    return [
        EvalResult(r.contract, r.passed, r.failures)
        for r, _ in ((evaluate_behavior(contract, trace), trace) for contract, trace in zip(contracts, traces))
    ]


def run_smoke_evals() -> list[EvalResult]:
    traces = {
        CASES[0].name: ["get_patients_by_name_and_phone"],
        CASES[1].name: ["get_patients_by_name_and_phone", "case_add"],
        CASES[2].name: ["get_product_list", "record_design_decision"],
        CASES[3].name: ["image_process"],
    }
    return [evaluate(case, traces[case.name]) for case in CASES]


def main() -> int:
    results = [*run_smoke_evals(), *run_behavior_contract_smoke()]
    for result in results:
        if result.passed:
            print(f"PASS {result.case}")
        else:
            print(f"FAIL {result.case}: {'; '.join(result.failures)}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
