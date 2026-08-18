# tools/face_management.py
import json
from typing import Optional, List, Annotated
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
from models import FaceBasicInfoTemplate
from models import BasePhotoInfoTemplate
from models import FaceModelInfoTemplate
from models.validators import with_model_validation, set_current_language
import logging

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("face_management")


@mcp.tool()
@with_model_validation(FaceBasicInfoTemplate, 'basic_info')
async def save_case_face(
        case_code: str = None,
        face_code: str = None,
        basic_info: Annotated[dict, "基础信息 / Basic Information"] = None,
        photo_info: BasePhotoInfoTemplate = None,
        model_info: FaceModelInfoTemplate = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """保存面诊信息 / Save Face Consultation Information

    保存或更新面诊的基础信息、影像资料和模型信息
    Save or update face consultation basic information, photos and model information

    **【重要】收集基础信息时 / 【IMPORTANT】When collecting basic information
        1:必须主动向用户展示完整选项列表(包含编号和内容)，并要求用户输入对应的编号 / you must proactively display the full list of options below (including numbers and content) to the user, and ask them to enter the corresponding number.
        2:必须主动询问用户 选择逐一引导 或 选择自主填写 / You must actively ask the user to either select 'one-by-one guidance' or choose 'manual entry'
        3:用户没有选择填写方式前，不要输出任何字段信息 / Do not output any field information until the user selects a fill method

        【根据用户选择执行】/ [Execute Based on User's Choice]
        选择逐一引导/guided:
        → 按顺序每次只问一个字段问题，等待回复后再继续下一个 / Ask one field question at a time in order
        选择自主填写/independent:
        → **仅**输出【一: 基础信息】模块下的所有字段列表（包含编号和选项）/ Output exclusively the field list for Module [I: Basic Information], including numbering and options
        → **严禁**在此步骤输出【二: 影像资料】或【三: 模型文件】的任何内容 / Strictly prohibit outputting any information regarding [II: Imaging Data] or [III: Model Files] in this step
        → 提示语示例：“好的，这是【基础信息】的所有字段，请您参考填写。填写完成后，我们再继续进行【影像资料】的收集” / "Alright, here is the complete list of fields for [Basic Information] for your reference. Once you've finished filling them out, we will proceed to collect the [Imaging Data]."

    **强制执行规则（必须遵守）/ Mandatory Rules (must comply):**
        1:你必须将收集过程严格切割为三个阶段（基础 -> 影像 -> 模型）/ "You are required to strictly isolate the collection process into three distinct stages: Basic -> Imaging -> Model."


    需要收集的核心字段（都是可选填，没有必填字段）:/ The core fields to be collected are all optional; there are no mandatory fields.
    一: 基础信息 / basic_info
    - appendix_exam:附件检查 / Attachment Examination(必须为整数。1-脱落, 2-完好 / Must be an integer. Options: 1-Detached, 2-Intact.)
    - op_type:临床操作 / Clinical Operation(必须为整数列表。1-片切, 2-拔牙, 3-粘贴附件。如 [1, 3] 表示做了片切和粘贴附件 / Must be a list of integers allowing multiple selections. Values: 1-IPR, 2-Extraction, 3-Attachment Bonding. For instance, [1, 3] represents performing both IPR and Attachment Bonding. )
    - orth_app_fitting:矫治器贴合 / Appliance fit (必须为整数。1-磨损, 2-无磨损, 3-未知 / Must be an integer. Options: 1-Worn, 2-Unworn, 3-Unknown)
    - patient_adherence:患者依从性 / Patient Compliance(必须为整数。1-优, 2-良, 3-差 / Must be an integer. 1-Excellent, 2-Fair, 3-Poor)
    - tooth_mob:牙齿松动度 / Tooth Mobility : (必须为整数。1-无松动, 2-I度, 3-II度, 4-III度 / Must be an integer.  1-(No Mobility), 2-(Class I), 3-(Class II), 4-(Class III).)
    - current_wearing_period:当前佩戴期数 / Current wearing period : (字符串或整数，如 "第5期" 或 5 / Must be a string or an integer. Examples: 'Phase 5' or 5.)。

    基础信息使用场景 / Basic Info Usage Scenarios:
    - 医生口述："病人CO20260116001复诊，附件完好，做了片切，依从性优。" -> 你需要提取上述字段并询问是否继续提供其余信息。/ Doctor's note: "Patient CO20260116001 returned for follow-up; attachments are intact, interproximal reduction (IPR) was performed, and compliance is excellent."
        Would you like to provide any additional information?
    - 如果用户只提供通用信息（如"牙疼"），请追问上述具体的数字化指标。/ If the user provides only general information (e.g., "toothache"), please follow up by asking for the specific digital metrics mentioned above

    二： 影像资料信息 / photo_info
    - face_open:患者口外照-正面开口微笑照片 / Patient extraoral photograph - frontal open-mouth smile view
    - face_close:患者口外照-正面闭合照片 / Patient extraoral photograph - frontal closed-lip view
    - face_side:患者口外照-侧立照片 / Patient extraoral photograph - lateral profile view
    - face_smile:患者口外照-侧45度微笑照片 / Patient extraoral photograph - 45-degree lateral smile view
    - mouth_upper:上颌照片 / Maxillary photo
    - mouth_lower:下颌照片 / Mandibular photo
    - mouth_cover:患者口内照-覆合覆盖照片 / Patient intraoral photograph - overbite view
    - mouth_front:患者口内照-正面咬合照片 / Patient intraoral photograph - frontal occlusion view
    - mouth_left:咬合左侧位照片 / Left lateral occlusion photograph
    - mouth_right:咬合右侧位照片 / Right lateral occlusion photograph
    - xray_front:患者X光片全颌曲面断层照片 / Patient panoramic radiograph
    - xray_side:患者X光片头颅侧位定位片 / Patient lateral cephalometric radiograph
    - cbct_file: CBCT文件 / CBCT file
    影像资料信息使用场景 / Photo Info Usage Scenarios:
    - 医生上传照片后 -> 你需要提取上述字段并调用此工具 / Trigger this tool by extracting the specified fields immediately after the doctor uploads a photo
    - **严格禁止在回复中输出任何 file_id、field_id、文件ID或哈希值（如 8c235...）。这些是系统内部参数，对用户不可见。** / **It is strictly forbidden to output any file_id, field_id, file ID, or hash values (e.g., 8c235...) in the response. These are internal system parameters and are invisible to the user**
    - **回复话术应仅关注业务内容**：请根据上传的照片类型（如“正面开口微笑照片”），用自然语言告知用户“已成功上传[照片类型]”，并直接展示图片缩略图 / The response should focus solely on business content: Please inform the user in natural language that "[photo type] uploaded successfully" based on the type of photo uploaded (e.g., 'frontal open-mouth smile photo'), and directly display the image thumbnail.
    - 如果用户没有提供全部影像信息，请追问是否继续提供其余的影像照片。/ If the user has not provided all imaging information, please follow up to ask whether to continue providing the remaining imaging photos.

    三：模型文件数据信息 / model_info
    - mouth_upper:上颌模型文件 / Maxillary model file
    - mouth_lower:下颌模型文件 / Mandibular model file
    - mouth_left:左侧咬合文件 / Left bite file
    - mouth_right:右侧咬合文件 / Right bite file
    - other_file:其它类型文件 / Other types of files
    模型文件信息使用场景 / Model Info Usage Scenarios:
    - 医生上传文件后 -> 你需要提取上述字段并调用此工具。/ After the doctor uploads the file, extract the aforementioned fields and invoke this tool.
    - 如果用户没有提供全部模型文件，请追问是否提供其余的模型文件。/ If the user has not provided all model files, please follow up to ask whether to provide the remaining model files.


    使用场景 / Usage Scenarios:
    - 初诊时创建面诊记录 / Create consultation record during initial visit
    - 复诊时更新面诊信息 / Update consultation information during follow-up visit
    - 补充面诊资料 / Supplement consultation materials

    Args:
        case_code: 病例编号 / Case number
        face_code: 面诊编号 / Face consultation code
        basic_info: 基础信息 / Basic information
        photo_info: 影像资料信息 / Photo information
        model_info: 模型文件数据信息 / Model file data information
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        保存结果 / Save result

    参数说明 / Parameter Notes:
    - case_code 和 face_code 至少提供一个 / At least one of case_code and face_code must be provided
    - basic_info、photo_info、model_info 可以单独或组合提供 / basic_info, photo_info, model_info can be provided separately or in combination
    """
    msg = "保存面诊信息" if we_lang == "zh-CN" else "Saving face consultation information"
    logger.info(f"{msg}: case_code={case_code}, lang={we_lang}")

    try:
        # 转换模型数据 / Convert model data
        basic_info_dict = basic_info.model_dump(exclude_unset=True) if basic_info else None
        photo_info_dict = photo_info.model_dump(exclude_unset=True) if photo_info else None
        model_info_dict = model_info.model_dump(exclude_unset=True) if model_info else None

        data = await orthodontic_service.save_case_face(
            case_code=case_code,
            face_code=face_code,
            basic_info=basic_info_dict,
            photo_info=photo_info_dict,
            model_info=model_info_dict,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "保存面诊信息失败" if we_lang == "zh-CN" else "Failed to save face consultation information"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "保存面诊信息时发生错误" if we_lang == "zh-CN" else "Error saving face consultation information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def case_face_list(
        keyword: str = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取面诊列表 / Get Face Consultation List

    根据关键词查询面诊记录列表（别名工具）
    Query face consultation record list by keyword (alias tool)

    使用场景 / Usage Scenarios:
    - 查看患者的所有面诊记录 / View all face consultation records for patient
    - 跟踪面诊历史 / Track consultation history

    Args:
        keyword: 患者姓名、手机号、编号或病例编号
                 Patient name, phone number, code or case number
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        面诊列表信息 / Face consultation list information
    """
    msg = "获取面诊列表" if we_lang == "zh-CN" else "Getting face consultation list"
    logger.info(f"{msg}: keyword={keyword}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_case_face_list(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "未获取到面诊列表" if we_lang == "zh-CN" else "Face consultation list not found"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取面诊列表时发生错误" if we_lang == "zh-CN" else "Error getting face consultation list"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def case_face_detail(
        keyword: str = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取面诊信息 / Get Face Consultation Details

    使用场景 / Usage Scenarios:
    - **最高优先级触发：** 只要用户输入中包含关键词 **面诊**，**必须**调用本工具。/ Top Priority Trigger: As long as the user input contains the keyword "Face Consultation", calling this tool is mandatory.
    - **排他性规则：** 本工具是查询面诊数据的**唯一**入口。/ Exclusivity Rule: This tool is the sole entry point for querying face consultation data
    - **严禁：** 任何涉及“面诊”的查询，**绝对禁止**调用 `get_patient_case_info`。/ Strictly Prohibited: Under no circumstances should get_patient_case_info be called for any query involving "Face Consultation".

    Args:
        keyword: 面诊 ID 或面诊编号 / Face consultation ID or face consultation code
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        面诊详情信息 / Face consultation details information
    """
    msg = "获取面诊详情" if we_lang == "zh-CN" else "Getting face consultation details"
    logger.info(f"{msg}: keyword={keyword}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_case_face_detail(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "未获取到面诊详情" if we_lang == "zh-CN" else "Face consultation details not found"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取面诊详情时发生错误" if we_lang == "zh-CN" else "Error getting face consultation details"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})