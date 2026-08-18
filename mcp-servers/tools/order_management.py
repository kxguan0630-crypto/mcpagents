# tools/order_management.py
import json


from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
from models import RecipeInfoTemplate
from models import CheckInfoTemplate
from models import ModelInfoTemplate
from models import PhotoInfoTemplate
from typing import Optional, Annotated
import logging

from models.validators import with_model_validation, set_current_language

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("order_management")


@mcp.tool()
@with_model_validation(CheckInfoTemplate, 'check_info')
@with_model_validation(RecipeInfoTemplate, 'recipe_info')
async def case_order_add(
        service_type: str,
        product_ids: list,
        product_type: str,
        case_code: str,
        need_design: int,
        model_info: Optional[ModelInfoTemplate] = None,
        check_info:  Annotated[dict, "临床诊断信息 / Clinical Diagnosis Information"] = None,
        photo_info: Optional[PhotoInfoTemplate] = None,
        recipe_info: Annotated[dict, "处方信息 / Prescription Information"] = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """创建新的正畸病例订单 / Create New Orthodontic Case Order

    创建订单的流程，必须按照以下步骤顺序执行 / Order creation process must follow these steps in order:

    **执行状态管理 / Execution State Management**
    当前执行状态 / Current State: STEP_1_CASE_CONFIRMED
    已完成步骤 / Completed Steps: []
    待执行步骤 / Pending Steps: [STEP_2, STEP_3, STEP_4, STEP_5, STEP_6, STEP_7, STEP_8, STEP_9]

    **状态定义 / State Definitions**
    STEP_1: 病例编号确认完成 / Case number confirmed
    STEP_2: 订单存在性检查完成 / Order existence check completed
    STEP_3: 产品列表获取完成 / Product list obtained
    STEP_4: 设计服务需求确认完成 / Design service requirement confirmed
    STEP_5: 临床诊断信息收集完成 / Clinical diagnosis information collected
    STEP_6: 影像资料收集完成 / Image data collected
    STEP_7: 模型信息收集完成 / Model information collected
    STEP_8: 处方信息收集完成 / Prescription information collected
    STEP_9: 订单提交完成 / Order submitted

    **强制执行规则（必须遵守）/ Mandatory Rules (must comply):**
    - 必须严格按照步骤 1→2→3→4→5→6→7→8 的顺序执行 / Must strictly follow steps 1→2→3→4→5→6→7→8 in order
    - 每一步都必须等待用户的明确回应后才能进入下一步 / Each step must wait for user's explicit response before proceeding
    - 严禁跳过任何步骤或提前进入后续步骤 / Skipping any steps or entering subsequent steps early is prohibited
    - 工具调用必须即时发生，不得延后或省略 / Tool calls must happen immediately, not delayed or omitted
    - 每一步完成后必须检查是否需要进入下一环节 / After each step completion, must check if next step is needed

    步骤 1 / Step 1. **确认病例编号 / Confirm Case Number**
       - 病例编号已确定为：{case_code} / Case number is determined: {case_code}
       - 该病例编号已自动关联对应患者信息，无需额外确认 / This case number is automatically linked to corresponding patient information
       - 注意：病例编号一旦确定不可更改 / Note: Case number cannot be changed once determined

    步骤 2 / Step 2. **检查是否已存在订单 / Check if Order Already Exists**
       - 如果病例编号case_code是新创建的,那么跳过此步骤2,进行下一步骤3 / If the case_code represents a newly created case, skip Step 2 and proceed directly to Step 3.
       - 调用工具`check_order_by_case_code`检查该病例是否已有关联订单 / Call tool `check_order_by_case_code` to check if case has associated order
       - 如果已经存在订单，必须立即终止流程并告知用户 / If order exists, immediately terminate process and inform user
       - 只有在确认无关联订单时，才能继续执行第 3 步 / Only proceed to step 3 when confirming no associated order

    步骤 3 / Step 3. **获取产品列表 / Get Product List**
       - 必须调用工具 `get_product_list`，获取当前可选的正式装产品 / Must call tool `get_product_list` to get current formal products
       - 向用户展示产品信息，必须包含：产品名称、产品编号、服务类型,价格、权益 / Show product information including: product name, product number,service type ,price, benefits
       - ⚠️ 重要：必须过滤并排除所有体验装产品 / Important: Must filter and exclude all trial products
         * 体验装产品特征 / Trial product characteristics:
           - 产品名称包含 "Trial"、"体验"、"试" 等关键词 / Product name contains keywords like "Trial", "体验", "试"
           - 产品类型标注为 "Trial Edition"、"体验版"、"试用装" / Product type marked as "Trial Edition", "体验版", "试用装"
         * 示例：Trial Kit (C11001)、体验装、试戴产品等都不可展示 / Examples: Trial Kit (C11001), 体验装，试戴 products must NOT be shown
       - 注意：必须保证产品价格的正确，不能有任何错误或偏差 / Note: Must ensure product prices are correct
       - 等待用户选择产品 / Wait for user to select product
       - **本步骤需要收集的参数 / Parameters to collect in this step:**
         * `service_type`: 从产品列表中获取的服务类型 / Service type from product list
         * `product_ids`: 从产品列表中选择的产品 ID 列表 / Selected product IDs from product list
         * `product_type`: 从产品列表中选择的产品类型 / Selected product type from product list

    步骤 4 / Step 4. **确认象贝设计服务需求 / Confirm Design Service Requirement**
       - 询问用户："是否需要象贝设计服务 (是/否)" / Ask user: "Do you need design service? (y/n)"
       - 若我选择"需要",请设置 `need_design = 1`，并自动添加矫正方案设计费的产品 / If "yes", set `need_design = 1` and add design fee product
       - 若我选择"不需要",请设置 `need_design = 0`，并询问："是否愿意提供处方信息？(y/n)" / If "no", set `need_design = 0` and ask: "Willing to provide prescription? (y/n)"

   步骤 5 / Step 5. **收集临床诊断信息 (`check_info`) / Collect Clinical Diagnosis Information**
       ⚠️⚠️⚠️ 绝对禁止行为 / ABSOLUTELY PROHIBITED BEHAVIORS:
       - 禁止在用户回答前展示任何字段、说明、引导内容 / Prohibited to show any fields, descriptions, or guidance before user answers
       - 禁止添加任何解释性文字（如"This information helps us..."、"If you answer yes..."等）/ Prohibited to add any explanatory text
       - 禁止预加载或暗示后续流程 / Prohibited to preload or hint at subsequent processes
       - 每次只输出纯粹的询问语句，不多一个字 / Output only the pure question, not a single extra word

       ❌ 错误示例 / WRONG EXAMPLES (严禁出现):
       - "是否愿意提供临床诊断信息？(y/n) This information helps us better understand..."
       - "Willing to provide clinical diagnosis information? (y/n) If you answer yes, I can..."
       - 任何包含解释、说明、背景信息的询问 / Any question containing explanations, descriptions, or background info

       ✅ 正确示例 / CORRECT EXAMPLES (必须遵循):
       - 中文："是否愿意提供临床诊断信息？(是/否)"
       - English: "Willing to provide clinical diagnosis information? (y/n)"

       ---

       执行流程 / Execution Flow:

       【第1次询问】/ [First Question]
       输出内容 / Output:
       - 中文模式："是否愿意提供临床诊断信息？(是/否)"
       - English mode: "Willing to provide clinical diagnosis information? (y/n)"

       ⚠️ 停止！等待用户回答 / STOP! Wait for user's response

       ---

       【分支判断】/ [Branch Logic]

       情况A：用户回答 否 / Case A: User answers n
       → 立即进入步骤6，不输出任何关于诊断的内容 / Immediately proceed to Step 6, output nothing about diagnosis

       情况B：用户回答 是 / Case B: User answers y
       → 继续第2次询问 / Continue to Second Question

       【第2次询问】/ [Second Question]
       输出内容 / Output:
       - 中文模式："您希望我逐一引导您填写，还是您自己查看字段后一次性提供？请回复 '逐一引导' 或 '自主填写' 。"
       - English mode: "Would you like me to guide you step by step, or would you prefer to view all fields and provide them at once? Please reply 'guided' or 'independent'."

       ⚠️ 禁止在此之前展示任何字段列表 / Prohibited to show any field lists before this
       ⚠️ 停止！等待用户回答 / STOP! Wait for user's response

       ---
       【根据用户选择执行】/ [Execute Based on User's Choice]

       选择逐一引导/guided:
       → 按顺序每次只问一个字段问题，等待回复后再继续下一个 / Ask one field question at a time in order

       选择自主填写/independent:
       → 展示完整的 CheckInfoTemplate 字段列表和说明 / Show complete CheckInfoTemplate field list and descriptions

       ---
       ⚠️ 重要：收集完诊断信息后，不要调用任何工具！继续步骤6 / Important: After collecting diagnosis info, do NOT call any tool! Continue to Step 6.

    步骤 6 / Step 6. **收集影像资料 (`photo_info`) / Collect Image Data**
       - 必须主动询问："是否愿意提供影像资料？(是/否)" / Must actively ask: "Willing to provide image data? (y/n)"
        - 若我表示愿意（回答 是） / If I agree (answer y):
         * 首先向我展示可上传的影像类型清单 / First show me the list of uploadable image types:

           可上传的影像类型包括 / Available image types include:
           • 口外照 / Extraoral photos:
             - face_open: 正面开口微笑照片 / Frontal open-mouth smile photo
             - face_close: 正面闭合照片 / Frontal closed-mouth photo
             - face_side: 侧立照片 / Lateral profile photo
             - face_smile: 侧45度微笑照片 / 45-degree smile photo

           • 口内照 / Intraoral photos:
             - mouth_upper: 上颌照片 / Upper jaw photo
             - mouth_lower: 下颌照片 / Lower jaw photo
             - mouth_cover: 覆合覆盖照片 / Overbite coverage photo
             - mouth_front: 正面咬合照片 / Frontal occlusion photo
             - mouth_left: 咬合左侧位照片 / Left lateral occlusion photo
             - mouth_right: 咬合右侧位照片 / Right lateral occlusion photo

           • X光片 / X-ray images:
             - xray_front: 全颌曲面断层照片 / Panoramic radiograph
             - xray_side: 头颅侧位定位片 / Cephalometric radiograph

           • 其他 / Others:
             - cbct_file: CBCT文件 / CBCT file
             - sign_one: 签名第一张照片 / Signature photo 1
             - sign_two: 签名第二张照片 / Signature photo 2
       - 若我表示愿意，必须先调用 `image_process` 工具处理图片 / If yes, must first call `image_process` tool to process images
       - 从返回结果中获取每个图片的 `fileId`、`imageType`、`score` 、`h`、`v`等信息 / Get `fileId`, `imageType`, `score` , `h` , `v` from response
       - 处理完成后询问："是否还需要上传其他影像资料？(y/n)" / After processing ask: "Need to upload more images? (y/n)"
       - 只有当我回答"n/否"时，才进入下一步 / Only proceed to next step when user answers "n/no"
       - ⚠️ 重要：收集完影像信息后，不要调用任何工具！继续下一步 / Important: After collecting image info, do NOT call any tool! Continue to next step.


    步骤 7 / Step 7. **收集模型信息 (`model_info`) / Collect Model Information**
       - 必须主动询问："是否愿意提供模型信息？(是/否)" / Must actively ask: "Willing to provide model information? (y/n)"
       - 若我表示愿意，调用工具`execute_command_open_ksapp`/ If I agree, call the tool execute_command_open_ksapp
       - ⚠️ 重要提醒 / Important reminders:
         * 模型文件只能通过口扫软件上传，不接受其他方式（如直接发送图片、文件等）/ Model files can ONLY be uploaded through the intraoral scanning software, other methods (such as sending images or files directly) are NOT accepted
         * 调用 `execute_command_open_ksapp` 后，不要立即进入下一步，需等待我确认上传完成 / After calling `execute_command_open_ksapp`, do not immediately proceed to next step, wait for my confirmation of upload completion
         * 收集完模型信息后，不要调用任何工具！继续下一步骤8 / After collecting model info, do NOT call any tool! Continue to step 8.

    步骤 8 / Step 8. **收集处方信息 (`recipe_info`) / Collect Prescription Information**
       - 若 need_design = 0, 必须主动询问："是否愿意提供处方信息？(是/否)" / If need_design = 0, must ask: "Willing to provide prescription? (y/n)"
       - 若我表示愿意，请进一步引导我提供处方信息 / If yes, guide user to provide prescription information
       - ⚠️ 重要：收集完处方信息后，不要调用任何工具！继续下一步 / Important: After collecting prescription info, do NOT call any tool! Continue to next step.


    步骤 9 / Step 9. **最终下单条件 / Final Order Submission Conditions**
       - 若 `need_design = 1`，必须帮助我添加矫正方案设计费的产品 / If `need_design = 1`, must add design fee product
       - 所有必填参数收集完成后，汇总并向我确认是否提交订单 / After collecting all required parameters, summarize and confirm with user
       - 当我确认提交订单时，必须实际调用 case_order_add 工具 / When user confirms order submission, must actually call case_order_add tool

    重要规则 / Important Rules:
    - 必须严格按照上述步骤顺序执行 / Must strictly follow above steps in order
    - 每一步都需要等待用户的明确回应 / Each step requires user's explicit response
    - 严禁在信息收集不完整时提示用户提交订单 / Prohibited to prompt order submission when information is incomplete

    Args:
        service_type: 服务类型/Service type
        product_ids: 产品 ID 列表/Product ID list
        product_type: 产品类型/Product type
        case_code: 病例编号/Case number
        need_design: 是否需要设计服务 (1-需要，0-不需要)/(1-yes, 0-no)
        model_info: 模型信息/Model information
        check_info: 临床诊断信息/Clinical diagnosis information
        photo_info: 医学影像信息/Medical image information
        recipe_info: 处方信息/Prescription information
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language (zh-CN/en-US)

    Returns:
        JSON 格式的创建结果，包含订单号等信息/Creation result in JSON format with order number etc.
    """
    lang_msg = "创建病例订单" if we_lang == "zh-CN" else "Creating case order"
    logger.info(f"{lang_msg}: case_code={case_code}, lang={we_lang}")
    print(f"请提供 {recipe_info}")

    # 验证象贝设计参数 / Validate design parameters
    if need_design == 1 and len(product_ids) != 2:
        msg = "需要象贝设计时，提交的产品参数中没有矫正方案设计费费用" if we_lang == "zh-CN" else "Design service selected but design fee product not included"
        return json.dumps({
            "message": msg,
            "code": 30000
        })

    try:
        # 转换模型数据 / Convert model data
        model_info_dict = model_info.model_dump(exclude_unset=True) if model_info else None
        check_info_dict = check_info.model_dump(exclude_unset=True) if check_info else None
        photo_info_dict = photo_info.model_dump(exclude_unset=True) if photo_info else None
        recipe_info_dict = recipe_info.model_dump(exclude_unset=True) if recipe_info else None

        data = await orthodontic_service.create_case_order(
            service_type=service_type,
            product_ids=product_ids,
            product_type=product_type,
            case_code=case_code,
            need_design=need_design,
            model_info=model_info_dict,
            check_info=check_info_dict,
            photo_info=photo_info_dict,
            recipe_info=recipe_info_dict,
            authorization=authorization,
            we_lang=we_lang
        )

        logger.info(f"{lang_msg}结果/Result: {data}")
        if not data:
            msg = "获取数据集格式不正确" if we_lang == "zh-CN" else "Dataset format is incorrect"
            return json.dumps({"message": msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "创建病例订单时发生错误" if we_lang == "zh-CN" else "Error creating case order"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
@with_model_validation(RecipeInfoTemplate, 'recipe_info')
async def save_recipe_info(keyword: str, recipe_info: Annotated[dict, "处方信息 / Prescription Information"], recipe_code: str = None,
                           authorization: str = None, we_lang: str = "zh-CN") -> str:
    """保存/提交处方信息 / Save/Submit Prescription Information

     ⚠️ 强制要求 / MANDATORY REQUIREMENT:
    在调用本工具之前，必须先调用 `check_recipe_editable_status` 工具检查订单状态！
    You MUST call `check_recipe_editable_status` tool BEFORE calling this tool!

    正确流程 / Correct Flow:
    1. 调用 check_recipe_editable_status(keyword) 检查处方可编辑状态
    2. 如果返回 editable=false，停止操作并告知用户
    3. 只有 editable=true 时，才能继续收集 recipe_info 并调用本工具

    请用户提供处方信息，按照 RecipeInfoTemplate 模型格式填写
    Ask user to provide prescription information in RecipeInfoTemplate format
    字段详细说明 / Detailed Field Descriptions:

    occlusal_guide_setting: 咬合导板设置  / Occlusal guide setting
                          - 枚举值 / Enum values: 1-无 (None), 2-放置位置 (Placement position)

    occlusal_guide_setting_column: 咬合导板放置的具体牙齿位置 / Specific tooth position for occlusal guide placement
                                   - 类型 / Type: ToothPosition (按象限分类的牙齿列表)
                                   - 必填条件 / Required when: occlusal_guide_setting=2

    spee_curve: Spee 曲线（纵颌曲线）处理策略 / Spee curve (curve of Spee) treatment strategy
                - 枚举值 / Enum values: 1-保持 (Maintain), 2-改善 (Improve), 3-完全整平 (Level completely)

    sagittal_left: 矢状向关系 - 左侧（尖牙和磨牙关系）/ Sagittal relationship - Left side (canine and molar relationship)
                   - 枚举值 / Enum values:
                     1-维持 (Maintain)
                     2-仅改善尖牙关系 (Improve canine only)
                     3-改善尖牙和磨牙关系 (Improve canine and molar)
                     4-调整到中性 (Adjust to neutral)

    sagittal_right: 矢状向关系 - 右侧（尖牙和磨牙关系）/ Sagittal relationship - Right side (canine and molar relationship)
                    - 枚举值 / Enum values: 同左侧 / Same as left side

    cover_relation: 覆盖关系（前后向覆盖）/ Cover relationship (anterior-posterior coverage)
                    - 枚举值 / Enum values: 1-维持 (Maintain), 2-改善 (Improve)

    overbite: 覆颌关系（垂直向覆盖）/ Overbite relationship (vertical coverage)
              - 枚举值 / Enum values:
                1-维持 (Maintain)
                5-压低上前牙改善 (Intrude upper anterior teeth)
                6-压低下前牙改善 (Intrude lower anterior teeth)
                7-伸长上前牙改善 (Extrude upper anterior teeth)
                8-伸长下前牙改善 (Extrude lower anterior teeth)

    anterior_crossbite: 前牙反颌/对刃矫正 / Anterior crossbite/edge-to-edge correction
                        - 枚举值 / Enum values: 1-维持 (Maintain), 2-纠正 (Correct)

    locking: 后牙反颌或锁颌是否需要矫治 / Posterior crossbite or locked occlusion correction needed
             - 枚举值 / Enum values: 1-是 (Yes), 2-否 (No)

    facial_method: 面型改善策略 / Facial profile improvement strategy
                   - 枚举值 / Enum values: 1-维持 (Maintain), 2-改善 (Improve)

    midline_upper: 上中线位置调整 / Upper midline position adjustment
                   - 枚举值 / Enum values:
                     1-维持 (Maintain)
                     2-向患者左侧移动 (Move to patient's left)
                     3-向患者右侧移动 (Move to patient's right)
                     4-根据方案确定 (Determine by plan)
                   - 必填条件 / Required when: 值为"2"或"3"

    midline_upper_length: 上中线移动距离（毫米）/ Upper midline movement distance (mm)
                          - 必填条件 / Required when: midline_upper in ("2", "3")

    midline_lower: 下中线位置调整 / Lower midline position adjustment
                   - 枚举值 / Enum values: 同上中线 / Same as upper midline
                   - 必填条件 / Required when: 值为"2"或"3"

    midline_lower_length: 下中线移动距离（毫米） / Lower midline movement distance (mm)
                          - 必填条件 / Required when: midline_lower in ("2", "3")

    crowd: 拥挤是否需要治疗 / Crowding treatment needed
           - 特殊值 / Special value: "none" - 不需要治疗 (No treatment needed)
           - 必填条件 / Required when: 不为"none"

    crowding_upper: 上颌拥挤治疗方案（可多选）/ Upper crowding treatment plan (multiple choice)
                    - 枚举值 / Enum values:
                      1-扩弓 (Expansion)
                      2-唇倾 (Labial inclination)
                      3-邻面去釉 (IPR - Interproximal Reduction)
                      4-磨牙远移 (Molar distalization)
                      5-拔牙 (Extraction)
                      none-不需要治疗 (No treatment needed)
                    - 格式 / Format: 逗号分隔的字符串 / Comma-separated string
                    - 必填条件 / Required when: crowd != "none"

    crowding_lower: 下颌拥挤治疗方案（可多选）/ Lower crowding treatment plan (multiple choice)
                    - 枚举值 / Enum values: 同上颌 / Same as upper
                    - 格式 / Format: 逗号分隔的字符串 / Comma-separated string
                    - 必填条件 / Required when: crowd != "none"

    space: 间隙处理策略 / Space management strategy
           - 枚举值 / Enum values: 1-全部关闭 (Close all), 2-间隙保留 (Reserve space)
           - 必填条件 / Required when: 值为"2"

    space_reserved_remark: 间隙保留的具体要求 / Space reservation requirements
                           - 必填条件 / Required when: space=2

    over_teeth: 是否需要过矫正 / Over-correction needed
                - 枚举值 / Enum values: 1-是 (Yes), 2-否 (No)
                - 必填条件 / Required when: 值为"1"

    over_teeth_other: 过矫正的特殊需求 / Special requirements for over-correction
                      - 必填条件 / Required when: over_teeth=1

    adjust_type: 矫正方法类型（可多选）/  Correction method type (multiple choice)
                 - 枚举值 / Enum values:
                   10-邻面去釉 (IPR)
                   20-磨牙远移 (Molar distalization)
                   30-扩弓 (Expansion)
                   40-拔牙 (Extraction)
                   50-根据 3D 方案 (According to 3D plan)
                   60-其它 (Other)
                 - 格式 / Format: 逗号分隔的字符串 / Comma-separated string
                 - 必填条件 / Required when: 包含"60"

    adjust_other: 当矫正类型为"其它"时的具体内容 / Specific content when correction type is "Other"
                  - 必填条件 / Required when: adjust_type 包含"60"

    target: 矫治目标及特殊说明 / Treatment objectives and special instructions


     交互模式 / Interaction Mode:
    1. 首先展示所有需要填写的字段列表及说明 / First display all required fields list and descriptions
    2. 询问用户是否希望逐一引导填写 / Ask if user wants guided question-by-question filling
    3. 如选择是，则按顺序每次只问一个问题，等待回复后再继续下一个 / If yes, ask one question at a time in order, wait for response before continuing
    4. 对于包含条件必填的字段，明确告知触发条件和输入要求 / For conditionally required fields, clearly state trigger conditions and input requirements
    5. 所有牙齿位置信息需按象限分类输入 / All tooth position information should be entered by quadrant
    6. 最终将收集的信息整理成 RecipeInfoTemplate 格式 / Finally organize collected information into RecipeInfoTemplate format


    使用场景 / Usage Scenarios:
    - 订单创建时提供处方信息 / Provide prescription when creating order
    - 阶段调整时提供处方信息 / Provide prescription during stage adjustment
    - 阶段调整时更新处方信息 / Update prescription during stage adjustment
    - 更新现有处方信息 / Update existing prescription

    要求 / Requirements:
    - 所有字段必须严格使用 RecipeInfoTemplate 的字段名 / All fields must strictly use RecipeInfoTemplate field names
    - 枚举型字段只能用数字表示 / Enum fields can only use numbers
    - 牙齿编号字段应为逗号分隔的字符串 / Tooth number fields should be comma-separated strings

    Args:
        keyword: 病例编号或订单编号/Case number or order number
        recipe_info: 处方信息/Prescription information
        recipe_code: 处方编码/正畸方案编号，更新处方时必填/Prescription code, required when updating
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        保存结果/Save result
    """
    msg = "保存处方信息" if we_lang == "zh-CN" else "Saving prescription information"
    logger.info(f"{msg}, keyword={keyword}")

    recipe_info_dict = recipe_info.model_dump(exclude_unset=True) if recipe_info else None
    try:
        data = await orthodontic_service.save_recipe_info(
            keyword=keyword,
            recipe_info=recipe_info_dict,
            recipe_code=recipe_code,
            authorization=authorization,
            we_lang=we_lang
        )
        logger.info(f"{msg}结果/Result: {data}")
        return json.dumps(data)
    except Exception as e:
        error_msg = "保存处方信息时发生错误" if we_lang == "zh-CN" else "Error saving prescription information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_order_list(
        keyword: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取订单列表 / Get Order List

    使用场景 / Usage Scenarios:
    - 根据患者姓名、手机号、编号或病例编号查询所有订单信息
      Query all order information by patient name, phone number, code or case number

    Args:
        keyword: 患者姓名、手机号、编号或病例编号/Patient name, phone, code or case number
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        订单列表信息/Order list information
    """
    msg = "获取订单列表" if we_lang == "zh-CN" else "Getting order list"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        data = await orthodontic_service.get_order_list(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "未获取到订单列表" if we_lang == "zh-CN" else "Order list not found"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取订单列表时发生错误" if we_lang == "zh-CN" else "Error getting order list"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def check_order_by_case_code(
        case_code: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取病例是否有关联的订单 / Check if Case Has Associated Order

    使用场景 / Usage Scenarios:
    - 根据病例编号查询主订单详细信息 / Query main order details by case number
    - 检查病例是否已有订单，用于订单创建流程 / Check if case already has order, used in order creation

    Args:
        case_code: 病例编号/Case number
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        订单信息/Order information
    """
    msg = "获取主订单信息" if we_lang == "zh-CN" else "Getting main order information"
    logger.info(f"{msg}: case_code={case_code}")

    try:
        data = await orthodontic_service.check_order_by_case_code(
            case_code=case_code,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "未获取到主订单信息" if we_lang == "zh-CN" else "Main order information not found"
            return json.dumps({"message": err_msg, "code": 30000})

        if isinstance(data, dict) and 'order_number' in data:
            if not data['order_number']:
                data['has_order'] = False
                data[
                    'message'] = "该病例目前没有关联的订单，可以新建。" if we_lang == "zh-CN" else "This case has no associated order, can create new one."
            else:
                data['has_order'] = True
                data[
                    'message'] = f"该病例已有关联订单：{data['order_number']}" if we_lang == "zh-CN" else f"This case has associated order: {data['order_number']}"

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取主订单信息时发生错误" if we_lang == "zh-CN" else "Error getting main order information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
@with_model_validation(CheckInfoTemplate, 'check_info')
async def save_check_info(
        keyword: str,
        check_info:  Annotated[dict, "临床诊断信息 / Clinical Diagnosis Information"],
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """保存临床诊断信息 / Save Clinical Diagnosis Information

    ⚠️ 强制要求 / MANDATORY REQUIREMENT:
    在调用本工具之前，必须先调用 `check_order_editable_status` 工具检查订单状态！
    You MUST call `check_order_editable_status` tool BEFORE calling this tool!

    正确流程 / Correct Flow:
    1. 调用 check_order_editable_status(keyword) 检查订单状态
    2. 如果返回 editable=false，停止操作并告知用户
    3. 只有 editable=true 时，才能继续收集 check_info 并调用本工具

    请用户提供患者的临床诊断信息，按照 CheckInfoTemplate 模型格式填写
    Ask user to provide clinical diagnosis information in CheckInfoTemplate format

    字段详细说明 | Detailed Field Descriptions:

    missing_teeth: 缺失牙齿情况
                   Missing teeth condition
                   - 枚举值 / Enum values:
                     1-无 (None)
                     2-以下牙齿缺失 (Teeth below missing)
                   - 必填条件 / Required when: 值为"2"

    missing_teeth_column: 缺失的具体牙齿位置
                          Specific missing tooth positions
                          - 类型 / Type: ToothPosition (按象限分类)
                          - 必填条件 / Required when: missing_teeth=2

    primary_teeth: 乳牙情况
                    Deciduous teeth condition
                    - 枚举值 / Enum values:
                      1-无 (None)
                      2-下牙齿为乳牙 (Teeth below are deciduous)
                    - 必填条件 / Required when: 值为"2"

    primary_teeth_column: 乳牙的具体位置
                          Specific deciduous tooth positions
                          - 类型 / Type: ToothPosition
                          - 必填条件 / Required when: primary_teeth=2


    oral_health: 口腔卫生状况
                 Oral hygiene condition
                 - 枚举值 / Enum values:
                   1-良好 (Good)
                   2-一般 (Fair)

    periodontal_health: 牙周健康状况
                        Periodontal health condition
                        - 枚举值 / Enum values:
                          1-良好 (Good)
                          2-一般 (Fair)


    molar_left: 左侧磨牙关系
                Left molar relationship
                - 枚举值 / Enum values:
                  1-I 类 (Class I) - 中性关系
                  2-II 类 (Class II) - 远中关系
                  3-III 类 (Class III) - 近中关系

    molar_right: 右侧磨牙关系
                 Right molar relationship
                 - 枚举值 / Enum values: 同左侧 / Same as left side

    canines_left: 左侧尖牙关系
                  Left canine relationship
                  - 枚举值 / Enum values:
                    1-中性 (Neutral) - 正常关系
                    2-远中 (Distal) - 尖牙向远中倾斜
                    3-近中 (Mesial) - 尖牙向近中倾斜

    canines_right: 右侧尖牙关系
                   Right canine relationship
                   - 枚举值 / Enum values: 同左侧 / Same as left side


    malocclusion_type: 错颌畸形类型（可多选）
                       Malocclusion type (multiple choice)
                       - 枚举值 / Enum values:
                         1-拥挤 (Crowding) - 牙量大于骨量
                         2-牙列间隙 (Spacing) - 牙齿间有缝隙
                         7-深覆盖 (Deep overjet) - 上前牙水平覆盖过大
                         8-深覆颌 (Deep overbite) - 上前牙垂直覆盖过大
                         9-前牙对刃/开颌 (Anterior edge-to-edge/Open bite) - 前牙无法咬合
                         11-中线不调 (Midline discrepancy) - 上下中线不齐
                         12-下颌前突 (Mandibular protrusion) - 地包天
                         14-上颌前突 (Maxillary protrusion) - 龅牙
                         15-上颌发育不足 (Maxillary deficiency) - 上颌骨发育不良
                         16-下颌后缩 (Mandibular retrusion) - 下颌后缩
                         17-反颌/锁颌 (Crossbite/Locked occlusion) - 反咬合
                         18-笑线不调 (Smile line discrepancy) - 微笑曲线不协调
                         13-其它 (Other) - 其他未列出的错颌类型
                       - 格式 / Format: 逗号分隔的字符串 / Comma-separated string
                       - 必填条件 / Required when: 包含"13"

    malocclusion_others: 其他错颌类型的详细描述
                         Detailed description of other malocclusion types
                         - 必填条件 / Required when: malocclusion_type 包含"13"


    facial_type: 侧面面型分类
                 Profile facial type classification
                 - 枚举值 / Enum values:
                   1-直面型 (Straight) - 侧貌直，美观
                   2-凹面型 (Concave) - 侧面凹陷，多为下颌前突
                   3-凸面型 (Convex) - 侧面凸起，多为上颌前突


    main_correct_goal: 主要矫治目标（可多选）
                       Main correction goals (multiple choice)
                       - 枚举值 / Enum values:
                         1-排齐牙齿 (Align teeth)
                         2-关闭牙列间隙 (Close spacing)
                         3-改善面型 (Improve facial profile)
                         4-纠正反颌 (Correct crossbite)
                         5-其他 (Other) - 其他特殊需求
                       - 格式 / Format: 逗号分隔的字符串 / Comma-separated string
                       - 必填条件 / Required when: 包含"5"

    main_correct_goal_others: 其他主要矫治目标的详细描述
                              Detailed description of other correction goals
                              - 必填条件 / Required when: main_correct_goal 包含"5"


    tooth_column: 治疗的牙颌范围
                  Treatment arch scope
                  - 枚举值 / Enum values:
                    1-上颌 (Maxilla) - 仅治疗上颌牙齿
                    2-下颌 (Mandible) - 仅治疗下颌牙齿
                    3-全颌 (Both archs) - 上下颌都治疗


    unmovable_teeth: 不可移动的牙齿情况
                     Unmovable teeth condition
                     - 枚举值 / Enum values:
                       1-无 (None) - 所有牙齿都可移动
                       2-以下牙齿不可移动 (Teeth below unmovable)
                     - 必填条件 / Required when: 值为"2"

    unmovable_teeth_column: 不可移动的具体牙齿位置
                            Specific unmovable tooth positions
                            - 类型 / Type: ToothPosition
                            - 必填条件 / Required when: unmovable_teeth=2

    unattach_teeth: 不可设计附件的牙齿情况
                    Teeth without attachments condition
                    - 枚举值 / Enum values:
                      1-无 (None) - 所有牙齿都可设计附件
                      2-以下牙齿不可设计附件 (Teeth below without attachments)
                    - 必填条件 / Required when: 值为"2"

    unattach_teeth_column: 不可设计附件的具体牙齿位置
                           Specific tooth positions without attachments
                           - 类型 / Type: ToothPosition
                           - 必填条件 / Required when: unattach_teeth=2


    is_grow_anchorage: 是否配合使用种植支抗钉
                       Whether to use implant anchorage screws
                       - 枚举值 / Enum values:
                         1-是 (Yes) - 需要使用支抗钉
                         2-否 (No) - 不使用支抗钉

    is_traction_device: 是否能接受佩戴牵引装置
                        Whether to accept traction devices
                        - 枚举值 / Enum values:
                          1-是 (Yes) - 可以接受牵引装置
                          2-否 (No) - 不能接受牵引装置


    is_mandible_abnormal: 颞下颌关节是否存在异常
                          Whether temporomandibular joint has abnormality
                          - 枚举值 / Enum values:
                            1-是 (Yes) - 存在关节异常
                            2-否 (No) - 关节正常

    extraction_teeth: 患者是否接受拔牙治疗
                      Whether patient accepts extraction treatment
                      - 枚举值 / Enum values:
                        1-否 (No) - 不接受拔牙
                        2-是 (Yes) - 接受拔牙
                        3-根据方案确定 (According to plan) - 由医生根据方案决定
                      - 必填条件 / Required when: 值为"2"

    extraction_teeth_column: 需要拔除的具体牙齿位置
                             Specific tooth positions to extract
                             - 类型 / Type: ToothPosition
                             - 必填条件 / Required when: extraction_teeth=2

    extraction_anchorage: 拔牙后的支抗控制策略
                          Anchorage control strategy after extraction
                          - 枚举值 / Enum values:
                            1-后牙强支抗 (Strong posterior anchorage) - 最大限度保持后牙位置
                            2-后牙中等支抗 (Moderate posterior anchorage) - 适度利用后牙支抗
                            3-后牙弱支抗 (Weak posterior anchorage) - 允许后牙适度前移

    is_receive_piece: 患者是否接受片切（邻面去釉）治疗
                      Whether patient accepts interproximal reduction (IPR)
                      - 枚举值 / Enum values:
                        1-是 (Yes) - 接受片切
                        2-否 (No) - 不接受片切

    other_description: 其他需要补充说明的情况
                       Other conditions that need supplementary explanation
                       - 自由文本 / Free text
                       - 可用于描述特殊病例情况、患者特殊需求等

    交互模式 / Interaction Mode:
    1. 首先展示所有需要填写的字段列表及说明 / First display all required fields list and descriptions
    2. 询问用户是否希望逐一引导填写 / Ask if user wants guided question-by-question filling
    3. 如选择是，则按顺序每次只问一个问题，等待回复后再继续下一个 / If yes, ask one question at a time in order, wait for response before continuing
    4. 对于包含条件必填的字段，明确告知触发条件和输入要求 / For conditionally required fields, clearly state trigger conditions and input requirements
    5. 所有牙齿位置信息需按象限分类输入 / All tooth position information should be entered by quadrant
    6. 最终将收集的信息整理成 CheckInfoTemplate 格式 / Finally organize collected information into CheckInfoTemplate format

    使用场景 / Usage Scenarios:
    - 为订单或病例添加临床诊断信息 / Add clinical diagnosis information to order or case
    - 更新现有的临床诊断信息 / Update existing clinical diagnosis information

    Args:
        keyword: 病例编号或订单编号/Case number or order number
        check_info: 临床诊断信息模板/Clinical diagnosis information template
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        保存结果/Save result
    """
    # 设置当前语言上下文 | Set current language context
    logger.debug(f"========================Setting current language: {we_lang}")
    print(f"================Setting current language: {we_lang}")
    set_current_language(we_lang)
    msg = "保存临床诊断信息" if we_lang == "zh-CN" else "Saving clinical diagnosis information"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        check_info_dict = check_info.model_dump(exclude_unset=True) if check_info else None

        data = await orthodontic_service.save_check_info(
            keyword=keyword,
            check_info=check_info_dict,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "保存临床诊断信息失败" if we_lang == "zh-CN" else "Failed to save clinical diagnosis information"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "保存临床诊断信息时发生错误" if we_lang == "zh-CN" else "Error saving clinical diagnosis information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})



@mcp.tool()
async def save_photo_info(
        keyword: str,
        photo_info: PhotoInfoTemplate,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """创建影像资料信息并提交保存 / Create and Save Image Data Information
    .⚠️ 强制要求 / MANDATORY REQUIREMENT:
     在调用本工具之前，必须先调用 `check_order_editable_status` 工具检查订单状态！
     You MUST call `check_order_editable_status` tool BEFORE calling this tool!

     正确流程 / Correct Flow:
     1. 调用 check_order_editable_status(keyword) 检查订单状态
     2. 如果返回 editable=false，停止操作并告知用户
     3. 只有 editable=true 时，才能继续收集 photo_info 并调用本工具

     可上传的影像类型包括 / Available image types include:
           • 口外照 / Extraoral photos:
             - face_open: 正面开口微笑照片 / Frontal open-mouth smile photo
             - face_close: 正面闭合照片 / Frontal closed-mouth photo
             - face_side: 侧立照片 / Lateral profile photo
             - face_smile: 侧45度微笑照片 / 45-degree smile photo

           • 口内照 / Intraoral photos:
             - mouth_upper: 上颌照片 / Upper jaw photo
             - mouth_lower: 下颌照片 / Lower jaw photo
             - mouth_cover: 覆合覆盖照片 / Overbite coverage photo
             - mouth_front: 正面咬合照片 / Frontal occlusion photo
             - mouth_left: 咬合左侧位照片 / Left lateral occlusion photo
             - mouth_right: 咬合右侧位照片 / Right lateral occlusion photo

           • X光片 / X-ray images:
             - xray_front: 全颌曲面断层照片 / Panoramic radiograph
             - xray_side: 头颅侧位定位片 / Cephalometric radiograph

           • 其他 / Others:
             - cbct_file: CBCT文件 / CBCT file
             - sign_one: 签名第一张照片 / Signature photo 1
             - sign_two: 签名第二张照片 / Signature photo 2

    使用流程 / Process:
    1. 先调用 `image_process` 工具处理图片 / First call `image_process` tool to process images
    2. 从返回结果中获取每个图片的 `fileId`、`imageType`、`score` 等信息 / Get `fileId`, `imageType`, `score` from response
    3. 按照上述格式组装成 `photo_info` 对象 / Assemble `photo_info` object according to the format

    使用场景 / Usage Scenarios:
    - 为订单或病例添加影像资料信息 / Add image data information to order or case
    - 更新现有的影像资料信息 / Update existing image data information

     特殊处理 / Special Handling:
    - 如果明确知道订单还没有创建，则不调用工具 `save_photo_info`，而是告知用户影像资料已经暂存
    - If it is clearly known that the order has not been created, do not call the `save_photo_info` tool, but inform the user that the image data has been temporarily stored

    Args:
        keyword: 病例编号或订单编号/Case number or order number
        photo_info: 影像资料信息模板/Image data information template
        authorization: 授权令牌/Authorization token


    Args:
        keyword: 病例编号或订单编号/Case number or order number
        photo_info: 影像资料信息模板/Image data information template
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        保存结果/Save result
    """
    msg = "保存影像资料信息" if we_lang == "zh-CN" else "Saving image data information"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        logger.info(f"{msg}: photo_info={photo_info.model_dump(exclude_unset=True) if photo_info else None}")

        data = await orthodontic_service.save_photo_info(
            keyword=keyword,
            photo_info=photo_info.model_dump(exclude_unset=True) if photo_info else None,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "保存影像资料信息失败" if we_lang == "zh-CN" else "Failed to save image data information"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "保存影像资料信息时发生错误" if we_lang == "zh-CN" else "Error saving image data information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_recipe_list(
        keyword: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取处方列表 / Get Prescription List

    使用场景 / Usage Scenarios:
    - 根据病例编号、订单编号、患者姓名、手机号或编号查询所有处方信息
      Query all prescription information by case number, order number, patient name, phone or code

    Args:
        keyword: 病例编号、订单编号、患者姓名、手机号或编号/Case number, order number, patient name, phone or code
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        处方列表信息/Prescription list information
    """
    msg = "获取处方列表" if we_lang == "zh-CN" else "Getting prescription list"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        data = await orthodontic_service.get_recipe_list(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "未获取到处方列表" if we_lang == "zh-CN" else "Prescription list not found"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取处方列表时发生错误" if we_lang == "zh-CN" else "Error getting prescription list"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_batch_product_list(
        keyword: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取发货批次和产品清单 / Get Shipping Batches and Product List

    使用场景 / Usage Scenarios:
    - 根据病例编号、订单编号、患者姓名、手机号或编号查询订单的发货批次和产品明细
      Query order shipping batches and product details by case number, order number, patient name, phone or code
    - 用户明确要求查询“发货信息”时 / When the user explicitly requests to query "shipping information"

    Args:
        keyword: 病例编号、订单编号、患者姓名、手机号或编号/Case number, order number, patient name, phone or code
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        发货批次和产品清单信息/Shipping batches and product list information
    """
    msg = "获取发货批次和产品清单" if we_lang == "zh-CN" else "Getting shipping batches and product list"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        data = await orthodontic_service.get_batch_product_list(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "未获取到发货批次和产品清单" if we_lang == "zh-CN" else "Shipping batches and product list not found"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取发货批次和产品清单时发生错误" if we_lang == "zh-CN" else "Error getting shipping batches and product list"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_pay_list(
        keyword: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取支付记录 / Get Payment Records

    通过患者姓名、或患者手机号、或患者编号、或病例编号查询支付记录
    Query payment records by patient name, phone number, code or case number

    要求 / Requirements:
    将全部数据整理后以结构化的方式展示，不要平铺展示
    Display all data in a structured way, do not display flatly

    使用场景 / Usage Scenarios:
    - 根据患者姓名、或患者手机号、或患者编号、或病例编号查询患者相关的所有支付记录
      Query all payment records related to patient by name, phone, code or case number

    Args:
        keyword: 患者姓名、或患者手机号、或患者编号、或病例编号/Patient name, phone, code or case number
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        支付记录列表/Payment record list
    """
    msg = "获取支付记录" if we_lang == "zh-CN" else "Getting payment records"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        data = await orthodontic_service.get_pay_list(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "未获取到支付记录" if we_lang == "zh-CN" else "Payment records not found"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取支付记录时发生错误" if we_lang == "zh-CN" else "Error getting payment records"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def order_apply_delivery(
        order_number: str,
        pair_count: int,
        consignee: str,
        consignee_address: str,
        consignee_mobile: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """根据订单编号申请发货 / Apply Delivery by Order Number

    调用流程：
    1：调用此工具前需要调用 get_order_remain_periods 工具，先检查一下该订单的矫治剩余期数是否大于 0
      Before calling this tool, need to call get_order_remain_periods to check if remaining periods > 0

    - 如果大于 0，则可以调用此工具申请发货(发货规则：8的倍数或者剩余全部副数) / If > 0, can call this tool to apply delivery(Ship in multiples of 8, or the remaining balance)
    - 如果小于等于 0，则提示用户该订单的矫治剩余期数不足，不能申请发货 / If <= 0, inform user that remaining periods are insufficient

    2：用户选择申请发货副数后,需要询问用户  收件人姓名，收货地址，联系电话 是否全部正确，是否需要修改(y/n)？
      After the user selects the Count  for the shipment application, please confirm with the user whether the recipient's name, shipping address, and contact phone number are all correct. Do any modifications need to be made?

    3：申请发货结束后，重新调用工具 get_batch_product_list。你必须以结构化的格式（最好是 Markdown 表格或详细列表）展示所有发货批次。不要对数据进行总结；要明确列出每一条记录
       After the shipping application is completed, re-call the tool get_batch_product_list. You must display ALL shipment batches in a structured format (preferably a Markdown Table or a detailed List). Do not summarize the data; list every single record explicitly

    Args:
        order_number: 订单编号/Order number
        pair_count: 制作后面发货副数 (发货期数)(0：代表制作后面全部)/Number of pairs to produce (0: all remaining)
        consignee: 收货人/Consignee
        consignee_address: 详细地址/Full address
        consignee_mobile: 联系电话/Contact phone
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        申请发货结果/Delivery application result
    """
    msg = "申请发货" if we_lang == "zh-CN" else "Applying delivery"
    logger.info(f"{msg}: order_number={order_number}")

    try:
        data = await orthodontic_service.apply_delivery(
            order_number=order_number,
            pair_count=pair_count,
            consignee=consignee,
            consignee_address=consignee_address,
            consignee_mobile=consignee_mobile,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "申请发货失败" if we_lang == "zh-CN" else "Delivery application failed"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "申请发货时发生错误" if we_lang == "zh-CN" else "Error applying delivery"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_order_remain_periods(
        order_number: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """查询订单的剩余副数 (剩余期数) 信息 / Query Order Remaining Periods

    Args:
        order_number: 订单编号/Order number
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        {
            "remain_periods": 剩余副数/Remaining periods,
            "consignee": 收货人/Consignee,
            "consignee_address": 详细地址/Full address,
            "consignee_mobile": 联系电话/Contact phone,
            "options": 发货方案/Delivery options
        }
    """
    msg = "查询订单的剩余副数" if we_lang == "zh-CN" else "Querying order remaining periods"
    logger.info(f"{msg}: order_number={order_number}")

    try:
        data = await orthodontic_service.get_order_remain_periods(
            order_number=order_number,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "获取数据失败" if we_lang == "zh-CN" else "Failed to get data"
            return json.dumps({"message": err_msg, "code": 30000})

        remain_periods = data['remain_periods']
        consignee = data['consignee']['contact_name']
        consignee_mobile = data['consignee']['contact_mobile']
        consignee_address = data['consignee']['contact_address']

        # 根据 remain_periods 生成选项 / Generate options based on remain_periods
        options = []
        if remain_periods < 8:
            options_cn = ["制作后面全部"]
            options_en = ["Produce all remaining"]
        else:
            # 生成 8 的倍数选项（最大不超过 32）/ Generate multiples of 8 options (max 32)
            options_cn = []
            options_en = []
            for i in range(1, 6):
                if i * 8 <= remain_periods:
                    options_cn.append(f"制作后面{i * 8}副")
                    options_en.append(f"Produce next {i * 8} pairs")
            options_cn.append("制作后面全部")
            options_en.append("Produce all remaining")

        # 根据语言选择选项数组 / Select options array based on language
        selected_options = options_cn if we_lang == "zh-CN" else options_en

        result = {
            "remain_periods": remain_periods,
            "consignee": consignee,
            "consignee_address": consignee_address,
            "consignee_mobile": consignee_mobile,
            "options": selected_options,
        }

        return json.dumps(result)

    except Exception as e:
        error_msg = "查询订单的剩余副数时发生错误" if we_lang == "zh-CN" else "Error querying order remaining periods"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def order_detail(
        order_number: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """查询订单详情 / Query Order Details

    照片直接展示给用户，不要显示超链接
    Display photos directly to user, do not show hyperlinks

    Args:
        order_number: 订单编号/Order number
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        订单详情信息/Order details information
    """
    msg = "查询订单详情" if we_lang == "zh-CN" else "Querying order details"
    logger.info(f"{msg}: order_number={order_number}")

    try:
        data = await orthodontic_service.get_order_detail(
            order_number=order_number,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "未获取到订单详情" if we_lang == "zh-CN" else "Order details not found"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "查询订单详情时发生错误" if we_lang == "zh-CN" else "Error querying order details"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def execute_command_open_ksapp(authorization: str = None, we_lang: str = "zh-CN") -> str:
    """上传口扫模型／启动口扫 / Upload Intraoral Scan Model or Start Scanning

    主要任务 / Main Task:
    - 当用户需要上传口扫模型或者启动口扫时，可以调用此工具
      Call this tool when user needs to upload intraoral scan model or start scanning
    - 根据返回结果，在用户浏览器端渲染出一个操作按钮
      Render an operation button in user's browser based on response
    - 按钮格式 / Button format: <button class='ai-custom-button' data-auto-action='{action}'>{title}</button>
      {action}和{title}的值从返回结果里获取 / Get {action} and {title} values from response
    - 不需要以 markdown 格式输出 / Do not output in markdown format

    Args:
        authorization: 授权令牌/Authorization token

    Returns:
        返回一个包含按钮 HTML 的 JSON 字符串/Returns a JSON string containing button HTML
    """
    msg = "执行开启口扫软件命令" if we_lang == "zh-CN" else "Executing command to open scanning software"
    logger.info(msg)

    try:
        data = await orthodontic_service.execute_command_open_ksapp(we_lang)

        if not data:
            err_msg = "执行开启口扫软件命令失败" if we_lang == "zh-CN" else "Failed to execute command to open scanning software"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "执行开启口扫软件命令时发生错误" if we_lang == "zh-CN" else "Error executing command to open scanning software"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_main_order_info(case_code: str, authorization: str = None,we_lang: str = "zh-CN"):
    """ 查询主订单信息
        Get Main Order Information

    使用场景 / Usage Scenarios:
        - 创建保持器订单时，需要先调用此工具，获取主订单信息 / When creating a retainer order, you must call this tool first to retrieve the primary order information

    Args:
        case_code:病例编号 / Case number
        authorization: 授权令牌/Authorization token
    Return:
         "order_number": 订单编号 /Order number
        "order_type_name": 订单类型 / Order type name
        "total_periods": 最大步数 / Total periods
        "upper_periods": 上颌最大步数 / Maxillary Maximum Steps
        "lower_periods": 下颌最大步数 / Mandibular Maximum Steps
        "sale_price": 保持器每副的价格 / Retainer Price per Set
    """

    # 查询主订单信息
    msg = "获取主订单信息" if we_lang == "zh-CN" else "Get Main Order Information"
    logger.info(f"{msg}: case_code={case_code}")

    try:
        data = await orthodontic_service.get_main_order_info(
            case_code=case_code,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "未获取到主订单信息" if we_lang == "zh-CN" else "Failed to retrieve main order information"
            return json.dumps({"message": err_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取主订单信息时发生错误" if we_lang == "zh-CN" else "Error getting Main Order Information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})

@mcp.tool()
async def check_order_editable_status(
        keyword: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """检查订单是否可编辑 / Check if Order is Editable

    ⚠️ 重要提示 / IMPORTANT:
    在修改订单相关信息(临床诊断、影像资料)之前,必须先调用此工具检查订单状态
    Before modifying order-related information (clinical diagnosis, images),
    you MUST call this tool first to check the order status.

    使用场景 / Usage Scenarios:
    - 在调用 save_check_info 前检查订单是否可编辑 / Check before calling save_check_info
    - 在调用 save_photo_info 前检查订单是否可编辑 / Check before calling save_photo_info
    - 任何需要修改订单信息的操作前都应该先检查 / Should check before any order modification

    执行流程 / Execution Flow:
    1. 用户提供病例编号或订单编号 / User provides case number or order number
    2. 调用本工具检查订单状态 / Call this tool to check order status
    3. 如果 editable=false,立即终止后续操作并告知用户 / If editable=false, immediately stop and inform user
    4. 只有 editable=true 时,才能继续收集信息和调用保存工具 / Only when editable=true, proceed to collect info and call save tools

    Args:
        keyword: 病例编号或订单编号/Case number or order number
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        JSON格式的检查结果 / Check result in JSON format:
        {
            "editable": true/false,  // 是否可编辑 / Whether editable
            "message": "提示信息"      // 友好的提示消息 / Friendly message
        }
    """
    msg = "检查订单可编辑状态" if we_lang == "zh-CN" else "Checking order editable status"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        data = await orthodontic_service.check_order_editable(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "无法获取订单状态" if we_lang == "zh-CN" else "Cannot get order status"
            return json.dumps({
                "editable": False,
                "message": err_msg,
                "code": 30000
            })

        editable = data.get('editable', False)
        # 根据可编辑状态生成友好提示
        if editable:
            if we_lang == "zh-CN":
                message = "✅ 订单当前可编辑，您可以继续修改相关信息。"
            else:
                message = "✅ Order is currently editable, you can continue to modify related information."
        else:
            if we_lang == "zh-CN":
                message = f"❌ 病例已经审核通过，不允许修改"
            else:
                message = f"❌ Case has been approved, no modification is allowed."

        result = {
            "editable": editable,
            "message": message
        }
        return json.dumps(result)

    except Exception as e:
        error_msg = "检查订单可编辑状态时发生错误" if we_lang == "zh-CN" else "Error checking order editable status"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({
            "editable": False,
            "message": f"{error_msg}: {str(e)}",
            "code": 50000
        })


@mcp.tool()
async def check_recipe_editable_status(
        keyword: str,
        recipe_code: str = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """检查处方是否可编辑 / Check if Recipe is Editable

    ⚠️ 重要提示 / IMPORTANT:
    在修改处方相关信息之前,必须先调用此工具检查处方状态
    Before modifying recipe information,
    you MUST call this tool first to check the recipe status.

    使用场景 / Usage Scenarios:
    - 在调用 save_recipe_info 前检查订单是否可编辑 / Check before calling save_recipe_info

    执行流程 / Execution Flow:
    1. 用户提供病例编号或订单编号 / User provides case number or order number
    2. 调用本工具检查处方是否可编辑 / Call this tool to check recipe is editable
    3. 如果 editable=false,立即终止后续操作并告知用户 / If editable=false, immediately stop and inform user
    4. 只有 editable=true 时,才能继续收集信息和调用保存工具 / Only when editable=true, proceed to collect info and call save tools

    Args:
        keyword: 病例编号或订单编号/Case number or order number
        recipe_code: 处方编号/Recipe code
        authorization: 授权令牌/Authorization token
        we_lang: 语言设置/Language

    Returns:
        JSON格式的检查结果 / Check result in JSON format:
        {
            "editable": true/false,  // 是否可编辑 / Whether editable
            "message": "提示信息"      // 友好的提示消息 / Friendly message
        }
    """
    msg = "检查处方是否可编辑" if we_lang == "zh-CN" else "Checking recipe is editable"
    logger.info(f"{msg}: keyword={keyword}")

    try:
        data = await orthodontic_service.check_recipe_editable(
            keyword=keyword,
            recipe_code=recipe_code,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            err_msg = "无法获取处方可编辑状态" if we_lang == "zh-CN" else "Cannot get recipe editable status"
            return json.dumps({
                "editable": False,
                "message": err_msg,
                "code": 30000
            })

        editable = data.get('recipe_editable', False)
        reason = data.get('reason', '')
        # 根据可编辑状态生成友好提示
        if editable:
            if we_lang == "zh-CN":
                message = "✅ 处方当前可编辑，您可以继续修改相关信息。"
            else:
                message = "✅ Recipe is currently editable, you can continue to modify related information."
        else:
            if we_lang == "zh-CN":
                message = f"❌ {reason}"
            else:
                message = f"❌ Recipe is not editable"

        result = {
            "editable": editable,
            "message": message
        }
        return json.dumps(result)

    except Exception as e:
        error_msg = "检查处方可编辑状态时发生错误" if we_lang == "zh-CN" else "Error checking recipe editable status"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({
            "editable": False,
            "message": f"{error_msg}: {str(e)}",
            "code": 50000
        })

