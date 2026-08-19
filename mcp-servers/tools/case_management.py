# tools/case_management.py
import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service

logger = logging.getLogger("SERVER_LOGGER")
mcp = FastMCP("case_management")


@mcp.tool()
async def get_patients_by_name_and_phone(
        patient_name: str,
        patient_phone: str,
        authorization: Optional[str] = None,
        we_lang: str = "zh-CN"
) -> str:
    """根据患者姓名和手机号查询患者是否存在。

    这是病例创建流程中的确定性查询 Tool。
    当客户端 Workflow 已完成患者基本信息和主诉收集后，必须调用本 Tool，
    不能仅向用户输出“正在查询”而不执行真实业务查询。

    返回值会保留业务接口结果，客户端根据真实结果推进 patient_checked 和查询结果状态。
    """
    logger.info(f"查询患者/Find patient: {patient_name}")
    try:
        data = await orthodontic_service.get_patients_by_name_and_phone(
            patient_name=patient_name,
            patient_phone=patient_phone,
            authorization=authorization,
            we_lang=we_lang,
        )
        return json.dumps({"code": 10000, "resultObject": data}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"查询患者失败/Find patient failed: {str(e)}")
        return json.dumps({"code": 50000, "message": str(e)}, ensure_ascii=False)


@mcp.tool()
async def case_add(
        patient_name: str,
        gender: int,
        patient_phone: str,
        age: str,
        new_a_patient: int,
        complaint: str,
        complaint_other: str = None,
        patient_code: str = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """创建病例 / Create a case.

    本 MCP Tool 只负责一次明确的“创建病例”业务动作。

    患者信息收集、主诉收集、患者存在性检查以及“新建/使用已有患者”的用户决策，
    由客户端 LangGraph Workflow 控制，不在这个 Tool 内执行多轮对话。

    参数约束：
    - patient_name、gender、patient_phone、age、new_a_patient、complaint 为必填；
    - new_a_patient=1 表示新建患者；
    - new_a_patient=2 表示使用已有患者，此时 patient_code 必须提供；
    - complaint_other 在主诉包含“其它”时提供；
    - authorization 为业务接口授权信息。

    本工具不会自行调用 get_patients_by_name_and_phone，也不会引导创建订单。
    """
    logger.info(f"创建病例/Create case: {patient_name}, 语言/Lang: {we_lang}")

    try:
        if new_a_patient not in (1, 2):
            return json.dumps({"code": 40000, "message": "new_a_patient must be 1 or 2"}, ensure_ascii=False)
        if new_a_patient == 2 and not patient_code:
            return json.dumps({"code": 40000, "message": "patient_code is required when using an existing patient"}, ensure_ascii=False)

        data = await orthodontic_service.case_add(
            patient_name=patient_name,
            gender=gender,
            patient_phone=patient_phone,
            age=age,
            new_a_patient=new_a_patient,
            complaint=complaint,
            complaint_other=complaint_other,
            patient_code=patient_code,
            authorization=authorization,
        )
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        logger.error(f"创建病例失败/Create case failed: {str(e)}")
        return json.dumps({"code": 50000, "message": str(e)}, ensure_ascii=False)
