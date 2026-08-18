# tools/case_management.py
import json
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
# from utils.logger import logger
import logging

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("case_management")


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
    """##新建病例 / Create New Case

    只收集患者基本信息包括患者姓名，性别，手机号，年龄，是否新增患者，主诉，其他主诉
    Collect basic patient information including name, gender, phone, age, new patient status, chief complaint

    新建病例流程，必须按照以下步骤顺序执行，不得跳过任一环节： / Creating a new case requires following these steps in order without skipping any
    1. 收集患者基本信息 / Collect basic patient info:
       - 姓名 (patient_name): 男→1, 女→2, 保密→3 / Male→1, Female→2, Confidential→3
       - 手机号 (patient_phone) / Phone number
       - 年龄 (age): 转为字符串 / Convert to string

    2. 【重要】收集患者主诉时，必须主动向用户展示以下完整选项列表（包含编号和内容），并要求用户输入对应的编号：
       【IMPORTANT】When collecting chief complaint, you MUST actively display the complete option list with numbers and content to the user, and ask them to input the corresponding numbers:

       接下来，请您告诉我患者的主诉（就诊原因），可以从以下选项中选择（可多选）：
       Please tell me the patient's chief complaint (reason for visit), you can choose from the following options (multiple choice allowed):

       1-牙齿不齐 / Crowded teeth
       2-反颌 / Crossbite
       3-调整微笑线 / Adjust smile line
       10-牙齿拥挤 / Teeth crowding
       20-牙间隙 / Tooth spacing
       30-地包天 / Underbite
       40-牙齿前突 / Protruding teeth
       50-其它 / Other

       请告诉我患者主诉对应的编号，例如"1,20"表示牙齿不齐和牙间隙。
       Please tell me the numbers corresponding to the patient's chief complaint, for example "1,20" means Crowded teeth and Tooth spacing.

       ⚠️ 注意：如果用户选择"50(其它)"，必须额外询问并记录 complaint_other 字段的具体内容
       ⚠️ Note: If user selects "50(Other)", you MUST additionally ask for and record the specific content in the complaint_other field

    3. 收集完患者信息后，必须调用工具 `get_patients_by_name_and_phone`，获取当前患者列表 / Must call get_patients_by_name_and_phone to check for existing patients
      如果已有相似患者，请展示给用户并请求确认或选择是否新建患者 / If similar patients already exist, display them to the user and request confirmation or ask whether to create a new patient.

    4. 如果选择新建患者，new_a_patient=1，否则=2
       If creating new patient, set new_a_patient=1, otherwise=2

    5. 如果 new_a_patient=2，patient_code 必填
       If new_a_patient=2, patient_code is required

    6. 确保所有必填字段完整后，调用 `case_add` 完成病例创建
       After ensuring all required fields are complete, call `case_add` to complete the case creation.

    7. 成功后引导用户是否创建订单
       After success, guide user whether to create order

    ### 必填参数 / Required Parameters:
    - patient_name, gender, patient_phone, age, new_a_patient, complaint

    ### 可选参数 / Optional Parameters:
    - complaint_other(当主诉为"其它"时必填/ Required when the chief complaint is "Other"), patient_code, authorization

    ### 注意事项：
    - 如果缺少任何必填参数，请主动向我提问获取。/ If any required parameters are missing
    - 对于主诉字段，请根据我的输入自动匹配对应的数字编号。/ For the chief complaint field, automatically match the corresponding number based on my input
    - 所有工具调用都应使用 JSON 格式返回，例如：/ ll tool calls should be returned in JSON format, for example:
       ```json
    {
      "tool": "case_add",
      "parameters": {
        "patient_name": "张三/ zhang san",
        "gender": 1,
        "patient_phone": "13800001111",
        "age": "25",
        "new_a_patient": 1,
        "complaint": "1,20,50",
        "complaint_other":"其它 / other "
      }
    }
    Args:
        patient_name: 患者姓名/Patient name
        gender: 性别 (1-男/Male, 2-女/Female, 3-保密/Confidential)
        patient_phone: 患者手机号/Patient phone
        age: 患者年龄/Patient age
        new_a_patient: (0-默认，1-新增，2-不新增)/(0-default, 1-new, 2-existing)
        complaint: 主诉数字编号/Chief complaint numeric code
        complaint_other: 其他主诉  默认为空　当患者主诉为其它时，输入的内容放入这个字段/Other chief complaint: Defaults to empty. When the patient's chief complaint is "Other", the input content should be placed in this field.
        patient_code: 患者编码/Patient code
        authorization: 授权令牌/Authorization token
        we_lang: 语言/Language (zh-CN/en-US)

    Returns:
       创建结果/Creation result
    """
    logger.info(f"创建病例/Create case: {patient_name}, 语言/Lang: {we_lang}")

    try:
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
            we_lang=we_lang
        )
        return json.dumps(data)
    except Exception as e:
        logger.error(f"创建病例错误/Error: {e}")
        msg = "创建病例时发生错误" if we_lang == "zh-CN" else "Error creating case"
        return json.dumps({"message": f"{msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_patients_by_name_and_phone(
        patient_name: str = None,
        patient_phone: str = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """【患者信息查询】根据姓名和手机号查询患者基本资料 / [Patient Query] Query basic patient info by name and phone

    ⚠️ 使用场景 / When to use:
    - 用户明确说"查询患者信息"、"查患者"、"找患者"时 / User says "query patient info", "find patient"
    - 需要确认患者是否存在于系统中 / Need to verify if patient exists in system
    - 新建病例前检查是否有重复患者 / Check for duplicate patients before creating new case
    - 仅返回患者基础信息：姓名、手机号、编号、性别、年龄 / Returns only basic info: name, phone, code, gender, age

    ✅ 典型对话示例 / Typical examples:
    - "查询管女士的患者信息" → 使用此工具 / "Query patient info for Ms. Guan" → Use this tool
    - "帮我找一下张三" → 使用此工具 / "Help me find Zhang San" → Use this tool
    - "13717825494这个号码有记录吗" → 使用此工具 / "Is there a record for 13717825494?" → Use this tool

    ❌ 不要在此场景使用 / Do NOT use when:
    - 用户要查看"病例详情"、"治疗方案"、"订单信息" → 应使用 get_patient_case_info / User wants "case details", "treatment plan", "order info" → Use get_patient_case_info instead
    - 用户提供的是病例编号而非患者信息 → 应使用 get_patient_case_info / User provides case number not patient info → Use get_patient_case_info instead

    ⚠️ 重要提示 / Important Note:
    - 患者姓名应保持原始输入,不要添加额外空格 / Keep patient name as original input, do not add extra spaces
    - 例如:"aa测试" 不应写成 "aa 测试" / For example: "aa测试" should NOT be written as "aa 测试"

    Args:
        patient_name: 患者姓名(保持原始格式,不加空格)/Patient name (keep original format, no extra spaces)
        patient_phone: 患者手机号/Patient phone
        authorization: 授权令牌/Authorization token
        we_lang: 语言/Language

    Returns:
        患者列表/Patient list
    """
    logger.info(f"查询患者/Query: name={patient_name}, phone={patient_phone}")

    try:
        data = await orthodontic_service.get_patients_by_name_and_phone(
            patient_name=patient_name,
            patient_phone=patient_phone,
            authorization=authorization,
            we_lang=we_lang
        )
        logger.info(f"查询结果/Result: {data}")

        if not data:
            msg = "未获取到患者信息" if we_lang == "zh-CN" else "Patient information not found"
            return json.dumps({"message": msg, "code": 30000})

        if isinstance(data, dict):
            count = data['count']
            if count == 0:
                data['has_patient'] = False
                data[
                    'message'] = "该患者在系统中尚无记录，我们将为其新建病例" if we_lang == "zh-CN" else "This patient has no record, we will create new case"
            else:
                data['has_patient'] = True
                data['message'] = "已查到该患者信息" if we_lang == "zh-CN" else "Patient information found"

        return json.dumps(data)
    except Exception as e:
        logger.error(f"查询患者错误/Error: {e}")
        msg = "查询患者时发生错误" if we_lang == "zh-CN" else "Error querying patient"
        return json.dumps({"message": f"{msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_patient_case_info(
        keyword: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取患者病例信息（**不包含**面诊数据）  / Get patient case information

    使用场景 / Usage Scenarios:
        - **适用范围：** 仅用于查询**普通**患者病例信息 / Scope of Application: Solely for querying general patient case information.
        - **排他性规则：** 只要用户输入中包含关键词 **面诊**，**必须**调用 `case_face_detail` / Exclusivity Rule: As long as the user input contains the keyword "Face Consultation", calling case_face_detail is mandatory.


    Args:
        keyword: 患者姓名、手机号、编号或病例编号/Patient name, phone, code or case number
        authorization: 授权令牌/Authorization token
        we_lang: 语言/Language

    Returns:
        患者病例信息/Patient case information
    """
    logger.info(f"获取病例信息/Get case info: keyword={keyword}")

    try:
        data = await orthodontic_service.get_patient_case_info(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            msg = "未获取到患者病例信息" if we_lang == "zh-CN" else "Patient case information not found"
            return json.dumps({"message": msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        logger.error(f"获取病例信息错误/Error: {e}")
        msg = "获取患者病例信息时发生错误" if we_lang == "zh-CN" else "Error getting patient case info"
        return json.dumps({"message": f"{msg}: {str(e)}", "code": 50000})
