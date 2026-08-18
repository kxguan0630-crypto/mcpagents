"""病例创建流程的可读定义。

注意：这里描述的是业务顺序，不直接执行 MCP Tool。
真正的运行时由 LangGraph 驱动，确定性门禁集中在 rules.py。
"""

CASE_CREATION_STEPS = (
    "collect_patient_info",
    "collect_complaint",
    "check_patient_exists",
    "wait_patient_decision",
    "create_case",
)

CASE_RULES = {
    "collect_patient_info": "患者姓名、性别、手机号、年龄必须完整。",
    "collect_complaint": "患者主诉必须完成收集；选择其它时必须有 complaint_other。",
    "check_patient_exists": "信息和主诉收集完成后，才允许调用 get_patients_by_name_and_phone。",
    "wait_patient_decision": "查询结果返回后，必须让用户决定新建患者还是使用已有患者。",
    "create_case": "只有完成患者检查和用户决策后才能调用 case_add；已有患者必须有 patient_code。",
}
