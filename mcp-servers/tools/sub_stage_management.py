# tools/sub_stage_management.py
import json
from typing import Annotated
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
from models import SubStageInfoTemplate
from models import CheckInfoTemplate
from models import ModelInfoTemplate
from models import PhotoInfoTemplate
from models import RecipeInfoTemplate
import logging
from models.validators import with_model_validation

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("sub_stage_management")


@mcp.tool()
@with_model_validation(CheckInfoTemplate, 'check_info')
@with_model_validation(RecipeInfoTemplate, 'recipe_info')
async def submit_stage_adjustment(
        case_code: str,
        order_number: str = None,
        sub_stage_info: SubStageInfoTemplate = None,
        check_info:  Annotated[dict, "临床诊断信息 / Clinical Diagnosis Information"] = None,
        photo_info: PhotoInfoTemplate = None,
        model_info: ModelInfoTemplate = None,
        recipe_info: Annotated[dict, "处方信息 / Prescription Information"] = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """申请阶段调整 / Apply Stage Adjustment

    执行流程（必须按顺序执行）/ Execution Process (must execute in order):

    【步骤 1 / Step 1】调用 get_stage_num 工具获取阶段调整信息
        Call get_stage_num tool to get stage adjustment information:
        - remain_num: 剩余调整次数 (-1 表示无限制) / Remaining adjustments (-1 means unlimited)
        - need_design: 是否需要象贝设计 (0=不需要，1=需要) / Need design service (0=no, 1=yes)
        - total_periods: 已发货的矫治器总副数 / Total delivered appliances
        - adjust_order_number: 正在进行完善信息的阶段调整订单编号 / Order number of ongoing stage adjustment

        终止条件 / Termination Conditions:
        - 如果 remain_num == 0 → 提示用户无法进行阶段调整 / If remain_num == 0 → inform user cannot do stage adjustment
        - 如果 adjust_order_number != "" → 提示用户无法进行阶段调整 / If adjust_order_number != "" → inform user cannot do stage adjustment

    【步骤 2 / Step 2】判断是否需要处方信息 / Determine if prescription information is needed
        - 如果 need_design == 0 → 询问用户是否提供处方信息 / If need_design == 0 → ask user for prescription information
        - 如果 need_design == 1→ 跳过此步骤 / If need_design == 1 → skip this step
        - ⚠️ 重要：收集完处方信息后，不要调用任何工具！继续下一步 / Important: After collecting prescription info, do NOT call any tool! Continue to next step.

    【步骤 3 / Step 3】收集阶段调整信息 (SubStageInfoTemplate) / Collect stage adjustment information
        必填字段 / Required Fields:
        - reason: 调整原因 / Adjustment reason
          枚举值 / Enum values:
          1-牙齿移动偏离原方案 / Teeth movement deviates from original plan
          2-患者做过新的修复或补牙 / Patient had new restoration or filling
          3-治疗方案改变 / Treatment plan changed
          4-治疗结束需要精细调整 / Fine adjustment needed at end of treatment
          5-患者依从性差佩戴时长不足 / Poor patient compliance, insufficient wearing time
        - appliance: 当前矫治器贴合情况 / Current appliance fit condition
          枚举值 / Enum values:
          1-矫治器贴合 / Appliance fits well
          2-矫治器不贴合 / Appliance doesn't fit
        - upper_step: 当前佩戴矫治器上颌步数 (范围：0 ~ total_periods) / Current upper step (range: 0 ~ total_periods)
        - lower_step: 当前佩戴矫治器下颌步数 (范围：0 ~ total_periods) / Current lower step (range: 0 ~ total_periods)

        可选字段 / Optional Fields:
        - remark: 设计要求备注 / Design requirement remarks

    【步骤 4 / Step 4】收集诊断信息 (CheckInfoTemplate) - 询问用户是否提供 / Collect diagnosis information - ask user if willing to provide
        枚举字段说明 / Enum Field Descriptions:
        - missing_teeth: 缺失牙齿 / Missing teeth (1-无/none, 2-以下牙齿缺失/below teeth missing)
        - missing_teeth_column: 缺失牙齿位置 / Missing tooth positions [当/when missing_teeth=2 时必填]
        - primary_teeth: 乳牙 / Primary teeth (1-无/none, 2-下牙齿为乳牙/lower teeth are primary)
        - primary_teeth_column: 乳牙位置 / Primary tooth positions [当/when primary_teeth=2 时必填]
        - oral_health: 口腔卫生 / Oral hygiene (1-良好/good, 2-一般/fair)
        - periodontal_health: 牙周状况 / Periodontal status (1-良好/good, 2-一般/fair)
        - molar_left: 磨牙关系左侧 / Molar relationship left (1-I 类/class I, 2-II 类/class II, 3-III 类/class III)
        - molar_right: 磨牙关系右侧 / Molar relationship right (1-I 类/class I, 2-II 类/class II, 3-III 类/class III)
        - canines_left: 尖牙关系左侧 / Canine relationship left (1-中性/neutral, 2-远中/distal, 3-近中/mesial)
        - canines_right: 尖牙关系右侧 / Canine relationship right (1-中性/neutral, 2-远中/distal, 3-近中/mesial)
        - malocclusion_type: 错颌类型 / Malocclusion type (多选/multiple choice: 1-拥挤/crowding, 2-牙列间隙/spacing, 7-深覆盖/deep overjet, 8-深覆颌/deep overbite, 9-前牙对刃/开颌/anterior crossbite/open bite, 11-中线不调/midline discrepancy, 12-下颌前突/mandibular protrusion, 14-上颌前突/maxillary protrusion, 15-上颌发育不足/maxillary deficiency, 16-下颌后缩/mandibular retrusion, 17-反颌/锁颌/crossbite/locked occlusion, 18-笑线不调/smile line discrepancy, 13-其它/other)
        - malocclusion_others: 错颌类型 - 其他描述 / Other malocclusion description [当/when malocclusion_type contains "13" 时必填]
        - facial_type: 面型 / Facial type (1-直面型/straight, 2-凹面型/concave, 3-凸面型/convex)
        - main_correct_goal: 主要矫治目标 / Main correction goal (多选/multiple choice: 1-排齐牙齿/align teeth, 2-关闭牙列间隙/close spacing, 3-改善面型/improve facial profile, 4-纠正反颌/correct crossbite, 5-其他/other)
        - main_correct_goal_others: 其他主要矫治目标 / Other main correction goals [当/when main_correct_goal contains "5" 时必填]
        - tooth_column: 治疗牙颌 / Treatment arch (1-上颌/maxilla, 2-下颌/mandible, 3-全颌/full arch)
        - unmovable_teeth: 不可移动牙齿 / Unmovable teeth (1-无/none, 2-以下牙齿不可移动/below teeth unmovable)
        - unmovable_teeth_column: 不可移动牙齿位置 / Unmovable tooth positions [当/when unmovable_teeth=2 时必填]
        - unattach_teeth: 不可设计附件牙齿 / Teeth without attachments (1-无/none, 2-以下牙齿不可设计附件/below teeth no attachments)
        - unattach_teeth_column: 不可设计附件牙齿位置 / No attachment tooth positions [当/when unattach_teeth=2 时必填]
        - is_grow_anchorage: 是否配合种植支抗钉 / Use TADs (1-是/yes, 2-否/no)
        - is_traction_device: 是否能接受牵引装置 / Accept traction device (1-是/yes, 2-否/no)
        - is_mandible_abnormal: 颞下颌关节是否存在异常 / TMJ abnormality (1-是/yes, 2-否/no)
        - extraction_teeth: 患者是否接受拔牙 / Extraction acceptance (1-否/no, 2-是/yes, 3-根据方案确定/depends on plan)
        - extraction_teeth_column: 拔除牙齿位置 / Extraction positions [当/when extraction_teeth=2 时必填]
        - extraction_anchorage: 拔牙 - 支抗 / Extraction anchorage (1-后牙强支抗/strong posterior anchorage, 2-后牙中等支抗/moderate posterior anchorage, 3-后牙弱支抗/weak posterior anchorage)
        - is_receive_piece: 患者是否接受片切 / Accept IPR (1-是/yes, 2-否/no)
        - other_description: 其他描述 / Other description

        - 首先询问："是否愿意提供临床诊断信息？(y/n)" / First ask: "Willing to provide clinical diagnosis information? (y/n)"
        - 若用户表示愿意，进一步询问引导方式 / If yes, ask preference:
          "您希望我逐一引导您填写，还是您自己查看字段后一次性提供？"
          "Would you like me to guide you step by step, or would you prefer to view all fields and provide them at once?"
        - 根据用户选择采用对应方式 / Use corresponding method based on user's choice:
          * 选择逐一引导 → 按顺序每次只问一个问题，等待回复后再继续下一个 / Choose guided → Ask one question at a time
          * 选择自主填写 → 展示所有字段列表和说明，等待用户提供 / Choose independent → Show all fields and wait
        - ⚠️ 重要：收集完诊断信息后，不要调用任何工具！继续下一步 / Important: After collecting diagnosis info, do NOT call any tool! Continue to next step.

    【步骤 5 / Step 5】收集影像信息 (PhotoInfoTemplate) - 询问用户是否提供 / Collect image information - ask user if willing to provide
        字段说明 / Field Descriptions:
        - face_open: 患者口外照 - 正面开口微笑照片 / Extraoral - frontal open smile
        - face_close: 患者口外照 - 正面闭合照片 / Extraoral - frontal closed
        - face_side: 患者口外照 - 侧立照片 / Extraoral - lateral
        - face_smile: 患者口外照 - 侧 45 度微笑照片 / Extraoral - 45-degree smile
        - mouth_upper: 上颌照片 / Intraoral - maxillary
        - mouth_lower: 下颌照片 / Intraoral - mandibular
        - mouth_cover: 患者口内照 - 覆合覆盖照片 / Intraoral - overbite overjet
        - mouth_front: 患者口内照 - 正面咬合照片 / Intraoral - frontal occlusion
        - mouth_left: 咬合左侧位照片 / Intraoral - left buccal occlusion
        - mouth_right: 咬合右侧位照片 / Intraoral - right buccal occlusion
        - xray_front: 患者 X 光片全颌曲面断层照片 / X-ray - panoramic
        - xray_side: 患者 X 光片头颅侧位定位片 / X-ray - cephalometric
        - cbct_file: CBCT 文件 / CBCT file
        - sign_one: 签名第一张照片 [正式装产品必填] / First signature photo [required for formal product]
        - sign_two: 签名第二张照片 [正式装产品必填] / Second signature photo [required for formal product]
        - ⚠️ 重要：收集完影像信息后，不要调用任何工具！继续下一步 / Important: After collecting image info, do NOT call any tool! Continue to next step.

    【步骤 6 / Step 6】收集模型信息 (ModelInfoTemplate) - 询问用户是否提供 / Collect model information - ask user if willing to provide
        字段说明 / Field Descriptions:
        - mouth_upper: 上颌模型文件 / Maxillary model file
        - mouth_lower: 下颌模型文件 / Mandibular model file
        - mouth_left: 左侧咬合文件 / Left buccal occlusion file
        - mouth_right: 右侧咬合文件 / Right buccal occlusion file
        - other_file: 其它类型文件 / Other file types

    【步骤 7 / Step 7】汇总并确认所有信息 / Summarize and confirm all information
        - 将收集到的所有信息整理成结构化格式 / Organize all collected information into structured format:
          * 阶段调整信息 / Stage adjustment information
          * 处方信息（如有）/ Prescription information (if provided)
          * 诊断信息（如有）/ Diagnosis information (if provided)
          * 影像信息（如有）/ Image information (if provided)
          * 模型信息（如有）/ Model information (if provided)
        - 向用户展示完整的信息摘要 / Show complete information summary to user
        - 询问用户："以上信息是否确认提交？(y/n)" / Ask user: "Confirm to submit the above information? (y/n)"
        - 只有当用户确认"y"后，才能进入下一步 / Only proceed to next step when user confirms "y"

    【步骤 8 / Step 8】调用 submit_stage_adjustment 工具提交申请 / Call submit_stage_adjustment tool to submit application
        - 将所有收集的信息作为参数传递 / Pass all collected information as parameters
        - 实际调用 submit_stage_adjustment 工具 / Actually call submit_stage_adjustment tool
        - 等待工具返回结果 / Wait for tool response

      ##重要规则 / Important Rules:
    - 必须严格按照上述步骤顺序执行 / Must strictly follow above steps in order
    - 每一步都需要等待用户的明确回应 / Each step requires user's explicit response
    - 严禁在信息收集不完整时提示用户申请阶段调整 / It is strictly prohibited to prompt the user to apply for stage adjustment when information collection is incomplete.

    Args:
        case_code: 病例编号 / Case number
        order_number: 订单编号 / Order number
        sub_stage_info: 阶段调整的信息 / Stage adjustment information
        check_info: 诊断信息 / Diagnosis information
        photo_info: 影像信息 / Image information
        model_info: 模型信息 / Model information
        recipe_info: 处方信息 / Prescription information
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        阶段调整申请后的成功信息 / Success message after stage adjustment application
    """
    msg = "提交阶段调整申请" if we_lang == "zh-CN" else "Submitting stage adjustment application"
    logger.info(f"{msg}: case_code={case_code}, lang={we_lang}")

    try:
        # 转换模型数据 / Convert model data
        sub_stage_info_dict = sub_stage_info.model_dump(exclude_unset=True) if sub_stage_info else None
        check_info_dict = check_info.model_dump(exclude_unset=True) if check_info else None
        photo_info_dict = photo_info.model_dump(exclude_unset=True) if photo_info else None
        model_info_dict = model_info.model_dump(exclude_unset=True) if model_info else None
        recipe_info_dict = recipe_info.model_dump(exclude_unset=True) if recipe_info else None

        data = await orthodontic_service.submit_stage_adjustment(
            case_code=case_code,
            order_number=order_number,
            sub_stage_info=sub_stage_info_dict,
            check_info=check_info_dict,
            photo_info=photo_info_dict,
            model_info=model_info_dict,
            recipe_info=recipe_info_dict,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "提交阶段调整申请失败" if we_lang == "zh-CN" else "Failed to submit stage adjustment application"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "提交阶段调整申请时发生错误" if we_lang == "zh-CN" else "Error submitting stage adjustment application"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_stage_num(
        case_code: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取剩余的阶段调整的次数以及上下颌步数和正在进行完善信息的阶段调整的订单 / Get Stage Adjustment Information

    查询剩余调整次数、是否需要设计服务以及正在进行的阶段调整订单
    Query remaining adjustments, design service requirement, and ongoing stage adjustment orders

    使用场景 / Usage Scenarios:
    - 开始阶段调整流程前检查资格 / Check eligibility before starting stage adjustment process
    - 查看患者的调整次数余额 / View patient's adjustment balance
    - 确认是否有正在进行的调整订单 / Confirm if there are ongoing adjustment orders

    Args:
        case_code: 病例编号 / Case number
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        {
            "total_periods": 已发货的矫治器总副数 / Total delivered appliances,
            "remain_num": 剩余的次数 / Remaining adjustments,
            "need_design": 是否需要象贝设计 / Need design service (0-no, 1-yes),
            "adjust_order_number": 正处于完善信息的阶段调整的订单编号 / Ongoing stage adjustment order number
        }

    返回值说明 / Return Value Notes:
    - remain_num = 0: 无法进行阶段调整 / Cannot do stage adjustment
    - remain_num = -1: 无限次调整 / Unlimited adjustments
    - adjust_order_number != "": 已有进行中的调整订单，需先完成 / Has ongoing adjustment order, must complete first
    """
    msg = "获取阶段调整次数信息" if we_lang == "zh-CN" else "Getting stage adjustment information"
    logger.info(f"{msg}: case_code={case_code}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_stage_num(
            case_code=case_code,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "获取阶段调整次数信息失败" if we_lang == "zh-CN" else "Failed to get stage adjustment information"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取阶段调整次数信息时发生错误" if we_lang == "zh-CN" else "Error getting stage adjustment information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})