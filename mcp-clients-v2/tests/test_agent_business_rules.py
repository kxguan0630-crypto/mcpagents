"""Agent 业务规则回归测试。

这些测试专门锁定两个容易导致 Agent 死循环的问题：
1. MCP HTTP 200 不等于业务 code=0；本项目查询 Tool 也可能返回 code=10000。
2. 患者查询成功后必须推进 patient_checked，不能重复查询同一个患者。
"""

from agent.workflows.rules import tool_result_succeeded, update_facts


def test_query_code_10000_is_success():
    """患者查询 Tool 使用 code=10000 时，应被识别为成功。"""
    result = '{"code": 10000, "resultObject": {"patients": [{"patientCode": "P001"}]}}'
    assert tool_result_succeeded(result) is True


def test_patient_query_updates_checked_state():
    """成功查询后，Workflow 应记录查询完成和患者存在结果。"""
    facts = {"patient_info_collected": True, "complaint_collected": True}
    result = '{"code": 10000, "resultObject": {"patients": [{"patientCode": "P001"}]}}'

    updated = update_facts(facts, "get_patients_by_name_and_phone", result)

    assert updated["patient_checked"] is True
    assert updated["patient_query_result"] == "found"


def test_failed_patient_query_does_not_advance_workflow():
    """查询失败时不能设置 patient_checked，否则会绕过确定性前置条件。"""
    facts = {"patient_info_collected": True, "complaint_collected": True}
    result = '{"code": 50000, "message": "token expired"}'

    updated = update_facts(facts, "get_patients_by_name_and_phone", result)

    assert updated.get("patient_checked") is not True
