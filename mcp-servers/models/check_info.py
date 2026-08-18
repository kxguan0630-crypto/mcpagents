from pydantic import BaseModel, ValidationError, Field, model_validator, field_validator
from typing import Optional, List
import re
from typing_extensions import Annotated
import logging
from .validators import _


VALID_TOOTH_RANGES = {
    'left_top': [(11, 18), (51, 55)],
    'right_top': [(21, 28), (61, 65)],
    'left_bottom': [(31, 38), (71, 75)],
    'right_bottom': [(41, 48), (81, 85)]
}


class ToothPosition(BaseModel):
    """
    牙齿位置定义 | Tooth Position Definition

    区域说明 | Region Description:
    - left_top: 左上颌 (left maxilla) - 恒牙 (permanent teeth): 11-18, 乳牙 (deciduous teeth): 51-55
    - right_top: 右上颌 (right maxilla) - 恒牙 (permanent teeth): 21-28, 乳牙 (deciduous teeth): 61-65
    - left_bottom: 左下颌 (left mandible) - 恒牙 (permanent teeth): 31-38, 乳牙 (deciduous teeth): 71-75
    - right_bottom: 右下颌 (right mandible) - 恒牙 (permanent teeth): 41-48, 乳牙 (deciduous teeth): 81-85

    注意 | Note: 乳牙使用 50+ 编号（如 55 表示左上颌第二乳磨牙）| Deciduous teeth use 50+ numbering (e.g., 55 represents left maxillary second deciduous molar)
    """
    left_top: List[int] = Field(default_factory=list, description=_("左上颌牙齿", "Left maxillary teeth"))
    right_top: List[int] = Field(default_factory=list, description=_("右上颌牙齿", "Right maxillary teeth"))
    left_bottom: List[int] = Field(default_factory=list, description=_("左下颌牙齿", "Left mandibular teeth"))
    right_bottom: List[int] = Field(default_factory=list, description=_("右下颌牙齿", "Right mandibular teeth"))

    @model_validator(mode='before')
    @classmethod
    def process_positions(cls, data):
        """
        核心逻辑：将输入数组中的每个元素分类到对应的牙位区间
        Core logic: Classify each element in the input array to the corresponding tooth position range
        """

        # 处理 None 值 | Handle None value
        if data is None:
            logger.debug("ToothPosition.process_positions handling None value")
            return {
                'left_top': [],
                'right_top': [],
                'left_bottom': [],
                'right_bottom': [],
            }

        # 处理字典格式（标准格式）| Handle dictionary format (standard format)
        if isinstance(data, dict):
            result = {
                'left_top': [],
                'right_top': [],
                'left_bottom': [],
                'right_bottom': [],
            }

            # 处理每个键值，确保它们是整数列表，并校验有效性
            # Process each key-value, ensure they are integer lists and validate
            for key in result.keys():
                if key in data:
                    if isinstance(data[key], list):
                        result[key] = []
                        for item in data[key]:
                            try:
                                tooth_num = int(item)
                                # 校验牙齿编号是否有效 | Validate tooth number
                                is_valid = False
                                for range_start, range_end in VALID_TOOTH_RANGES[key]:
                                    if range_start <= tooth_num <= range_end:
                                        is_valid = True
                                        break

                                if is_valid:
                                    result[key].append(tooth_num)
                                else:
                                    raise ValueError(_(
                                        f"无效的牙齿位置：{tooth_num} 不属于 {key} 区域",
                                        f"Invalid tooth position: {tooth_num} does not belong to {key} region"
                                    ))
                            except (ValueError, TypeError) as e:
                                raise ValueError(_(
                                    f"牙齿位置数据格式错误：{str(e)}",
                                    f"Tooth position data format error: {str(e)}"
                                ))
                    elif data[key] is None:
                        result[key] = []
                    elif isinstance(data[key], str):
                        # 处理字符串形式的列表 | Handle string format list
                        if data[key].strip():
                            nums = [int(x.strip()) for x in data[key].split(',') if x.strip().isdigit()]
                            result[key] = nums
                        else:
                            result[key] = []
            return result

        # 处理字符串格式（来自 MCP 参数的常见情况）| Handle string format (common case from MCP parameters)
        if isinstance(data, str):
            data = data.strip()
            if not data:  # 空字符串 | Empty string
                return {
                    'left_top': [],
                    'right_top': [],
                    'left_bottom': [],
                    'right_bottom': [],
                }

            # 分割字符串并转换为数字 | Split string and convert to numbers
            tooth_nums = []
            separators = r'[;,,、\s]+'  # 支持多种分隔符 | Support multiple separators
            parts = re.split(separators, data)

            for part in parts:
                part = part.strip()
                if part and part.isdigit():
                    tooth_nums.append(int(part))

            # 分类到各个区域 | Classify to each region
            result = {
                'left_top': [],
                'right_top': [],
                'left_bottom': [],
                'right_bottom': [],
            }

            for num in tooth_nums:
                if (11 <= num <= 18) or (51 <= num <= 55):
                    result['left_top'].append(num)
                elif (21 <= num <= 28) or (61 <= num <= 65):
                    result['right_top'].append(num)
                elif (31 <= num <= 38) or (71 <= num <= 75):
                    result['left_bottom'].append(num)
                elif (41 <= num <= 48) or (81 <= num <= 85):
                    result['right_bottom'].append(num)
                else:
                    raise ValueError(_(
                        f"牙位错误：{num}，请确认后重新输入",
                        f"Invalid tooth position: {num}, please confirm and re-enter"
                    ))

            return result

        # 处理列表格式 | Handle list format
        if isinstance(data, list):
            result = {
                'left_top': [],
                'right_top': [],
                'left_bottom': [],
                'right_bottom': [],
            }

            for item in data:
                try:
                    num = int(item)
                    if (11 <= num <= 18) or (51 <= num <= 55):
                        result['left_top'].append(num)
                    elif (21 <= num <= 28) or (61 <= num <= 65):
                        result['right_top'].append(num)
                    elif (31 <= num <= 38) or (71 <= num <= 75):
                        result['left_bottom'].append(num)
                    elif (41 <= num <= 48) or (81 <= num <= 85):
                        result['right_bottom'].append(num)
                    else:
                        raise ValueError(_(
                            f"牙位错误：{num}，请确认后重新输入",
                            f"Invalid tooth position: {num}, please confirm and re-enter"
                        ))
                except (ValueError, TypeError):
                    raise ValueError(_(
                        f"不合法的牙齿位：{item}，牙齿位必须为数字，请重新输入",
                        f"Invalid tooth position: {item}, must be numeric"
                    ))

            return result

        raise ValueError(_(
            f"牙齿位置数据必须是字典、列表或可分割的字符串，当前类型为：{type(data)}",
            f"Tooth position data must be dictionary, list or separable string, current type is {type(data)}"
        ))

    @model_validator(mode='wrap')
    @classmethod
    def wrap_validator(cls, values, handler):
        """
        包装验证器，确保所有输入都能被正确处理
        Wrapper validator, ensure all inputs can be processed correctly
        """
        try:
            # 首先尝试标准验证 | Try standard validation first
            result = handler(values)
            return result
        except Exception as e:
            # 如果标准验证失败，尝试我们的自定义处理
            # If standard validation fails, try our custom processing
            try:
                processed_values = cls.process_positions(values)
                result = handler(processed_values)
                return result
            except Exception as inner_e:
                raise ValueError(_(
                    f"无法处理输入数据：{str(inner_e)}",
                    f"Unable to process input data: {str(inner_e)}"
                ))

    class Config:
        """
        配置类 | Configuration Class
        """
        # 启用额外的验证选项 | Enable extra validation options
        extra = "forbid"
        # 启用严格的类型检查 | Enable strict type checking
        validate_assignment = True


class BaseCheckInfoTemplate(BaseModel):
    """
    临床诊断信息模板 - 用于收集患者口腔检查信息
    Clinical Diagnosis Information Template - Used to collect patient oral examination data

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
                         5-其他 (Other)
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
                       - 可用于描述特殊病例情况、患者特殊需求等
    使用场景 | Use Cases:
    - 订单创建时收集临床诊断信息 | Collect clinical diagnosis when creating order
    - 阶段调整时收集临床诊断信息 | Collect clinical diagnosis during stage adjustment
    - 更新诊断信息时收集临床诊断信息 | Collect clinical diagnosis when updating diagnosis

    字段说明 | Field Description:
    - 带有 "|" 符号的字段为枚举类型，冒号后为可选值 | Fields with "|" are enum types, options after colon
    - 带有 "以下牙齿" 字样的字段需要配合其对应的开关字段使用 | Fields with "teeth below" need to be used with their corresponding switch fields
    - 所有牙齿位置字段使用 ToothPosition 结构 | All tooth position fields use ToothPosition structure

    条件必填字段 | Conditional Required Fields:
    - missing_teeth=2 时，missing_teeth_column 必填 | When missing_teeth=2, missing_teeth_column is required
    - primary_teeth=2 时，primary_teeth_column 必填 | When primary_teeth=2, primary_teeth_column is required
    - unmovable_teeth=2 时，unmovable_teeth_column 必填 | When unmovable_teeth=2, unmovable_teeth_column is required
    - unattach_teeth=2 时，unattach_teeth_column 必填 | When unattach_teeth=2, unattach_teeth_column is required
    - extraction_teeth=2 时，extraction_teeth_column 必填 | When extraction_teeth=2, extraction_teeth_column is required
    - main_correct_goal 包含"5"时，main_correct_goal_others 必填 | When main_correct_goal contains "5", main_correct_goal_others is required
    - malocclusion_type 包含"13"时，malocclusion_others 必填 | When malocclusion_type contains "13", malocclusion_others is required
    """

    # 必填字段 | Required fields
    missing_teeth: Optional[str] = Field(None,
                                         description=_(
                                             "缺失牙齿 | Missing teeth | 1:无 (none) 2:以下牙齿缺失 (teeth below missing)",
                                             "Missing teeth | 1:None 2:Teeth below missing"))
    missing_teeth_column: Optional[ToothPosition] = Field(default_factory=ToothPosition,
                                                          description=_("以下牙齿缺失", "Teeth below missing"))
    primary_teeth: Optional[str] = Field(None,
                                         description=_(
                                             "乳牙 | Deciduous teeth | 1:无 (none) 2:下牙齿为乳牙 (teeth below are deciduous)",
                                             "Deciduous teeth | 1:None 2:Teeth below are deciduous"))
    primary_teeth_column: Optional[ToothPosition] = Field(default_factory=ToothPosition,
                                                          description=_("以下牙齿为乳牙", "Teeth below are deciduous"))
    oral_health: Optional[str] = Field(None,
                                       description=_("口腔卫生 | Oral hygiene | 1-良好 (good) 2-一般 (fair)",
                                                     "Oral hygiene | 1-Good 2-Fair"))
    periodontal_health: Optional[str] = Field(None,
                                              description=_(
                                                  "牙周状况 | Periodontal condition | 1-良好 (good) 2-一般 (fair)",
                                                  "Periodontal condition | 1-Good 2-Fair"))
    molar_left: Optional[str] = Field(None,
                                      description=_(
                                          "磨牙关系左侧 | Molar relationship left | 1-I 类 (Class I) 2-II 类 (Class II) 3-III 类 (Class III)",
                                          "Molar relationship left | 1-Class I 2-Class II 3-Class III"))
    molar_right: Optional[str] = Field(None,
                                       description=_(
                                           "磨牙关系右侧 | Molar relationship right | 1-I 类 (Class I) 2-II 类 (Class II) 3-III 类 (Class III)",
                                           "Molar relationship right | 1-Class I 2-Class II 3-Class III"))
    canines_left: Optional[str] = Field(None,
                                        description=_(
                                            "尖牙关系左侧 | Canine relationship left | 1-中性 (neutral) 2-远中 (distal) 3-近中 (mesial)",
                                            "Canine relationship left | 1-Neutral 2-Distal 3-Mesial"))
    canines_right: Optional[str] = Field(None,
                                         description=_(
                                             "尖牙关系右侧 | Canine relationship right | 1-中性 (neutral) 2-远中 (distal) 3-近中 (mesial)",
                                             "Canine relationship right | 1-Neutral 2-Distal 3-Mesial"))
    malocclusion_type: Annotated[
        Optional[List[str]],
        Field(
            description=_(
                "错颌类型 | Malocclusion type | 1-拥挤 (crowding) 2-牙列间隙 (spacing) 7-深覆盖 (deep overjet) 8-深覆颌 (deep overbite) 9-前牙对刃/开颌 (anterior edge-to-edge/open bite) 11-中线不调 (midline discrepancy) 12-下颌前突 (mandibular protrusion) 14-上颌前突 (maxillary protrusion) 15-上颌发育不足 (maxillary deficiency) 16-下颌后缩 (mandibular retrusion) 17-反颌/锁颌 (crossbite/locked occlusion) 18-笑线不调 (smile line discrepancy) 13-其它 (other)",
                "Malocclusion type | 1-Crowding 2-Spacing 7-Deep overjet 8-Deep overbite 9-Anterior crossbite/open bite 11-Midline discrepancy 12-Mandibular protrusion 14-Maxillary protrusion 15-Maxillary deficiency 16-Mandibular retrusion 17-Crossbite/locked occlusion 18-Smile line discrepancy 13-Other"))
    ] = None
    malocclusion_others: Optional[str] = Field(None,
                                               description=_("错颌类型 - 其他", "Malocclusion type - other"))
    facial_type: Optional[str] = Field(None,
                                       description=_(
                                           "面型 | Facial type | 1-直面型 (straight) 2-凹面型 (concave) 3-凸面型 (convex)",
                                           "Facial type | 1-Straight 2-Concave 3-Convex"))
    main_correct_goal: Annotated[
        Optional[List[str]],
        Field(
            description=_(
                "主要矫治目标 | Main correction goals | 1-排齐牙齿 (align teeth) 2-关闭牙列间隙 (close spacing) 3-改善面型 (improve facial profile) 4-纠正反颌 (correct crossbite) 5-其他 (other)",
                "Main correction goals | 1-Align teeth 2-Close spacing 3-Improve facial profile 4-Correct crossbite 5-Other"))
    ] = None
    main_correct_goal_others: Optional[str] = Field(None,
                                                    description=_("其他主要矫治目标", "Other main correction goals"))
    tooth_column: Optional[str] = Field(None,
                                        description=_(
                                            "治疗牙颌 | Treatment arch | 1-上颌 (maxilla) 2-下颌 (mandible) 3-全颌 (both archs)",
                                            "Treatment arch | 1-Maxilla 2-Mandible 3-Both archs"))
    unmovable_teeth: Optional[str] = Field(None,
                                           description=_(
                                               "不可移动牙齿 | Unmovable teeth | 1:无 (none) 2:以下牙齿不可移动 (teeth below unmovable)",
                                               "Unmovable teeth | 1:None 2:Teeth below unmovable"))
    unmovable_teeth_column: Optional[ToothPosition] = Field(default_factory=ToothPosition,
                                                            description=_("不可移动牙齿", "Unmovable teeth"))
    unattach_teeth: Optional[str] = Field(None,
                                          description=_(
                                              "不可设计附件牙齿 | Teeth without attachments | 1:无 (none) 2:以下牙齿不可设计附件 (teeth below without attachments)",
                                              "Teeth without attachments | 1:None 2:Teeth below without attachments"))
    unattach_teeth_column: Optional[ToothPosition] = Field(default_factory=ToothPosition,
                                                           description=_("不可设计附件牙齿",
                                                                         "Teeth without attachments"))
    is_grow_anchorage: Optional[str] = Field(None,
                                             description=_(
                                                 "是否配合种植支抗钉 | Whether to use implant anchorage | 1:是 (yes) 2:否 (no)",
                                                 "Whether to use implant anchorage | 1:Yes 2:No"))
    is_traction_device: Optional[str] = Field(None,
                                              description=_(
                                                  "是否能接受牵引装置 | Whether to accept traction device | 1:是 (yes) 2:否 (no)",
                                                  "Whether to accept traction device | 1:Yes 2:No"))
    is_mandible_abnormal: Optional[str] = Field(None,
                                                description=_(
                                                    "颞下颌关节是否存在异常 | Whether temporomandibular joint has abnormality | 1:是 (yes) 2:否 (no)",
                                                    "Whether temporomandibular joint has abnormality | 1:Yes 2:No"))
    extraction_teeth: Optional[str] = Field(None,
                                            description=_(
                                                "患者是否接受拔牙 | Whether patient accepts extraction | 1-否 (no) 2-是 (yes) 3-根据方案确定 (according to plan)",
                                                "Whether patient accepts extraction | 1-No 2-Yes 3-According to plan"))
    extraction_teeth_column: Optional[ToothPosition] = Field(default_factory=ToothPosition,
                                                             description=_("患者是否接受拔牙 - 拔除以下牙齿",
                                                                           "Whether patient accepts extraction - extract teeth below"))
    extraction_anchorage: Optional[str] = Field(None,
                                                description=_(
                                                    "拔牙 - 支抗 | Extraction - anchorage | 1-后牙强支抗 (strong posterior anchorage) 2-后牙中等支抗 (moderate posterior anchorage) 3-后牙弱支抗 (weak posterior anchorage)",
                                                    "Extraction - anchorage | 1-Strong posterior anchorage 2-Moderate posterior anchorage 3-Weak posterior anchorage"))
    is_receive_piece: Optional[str] = Field(None,
                                            description=_(
                                                "患者是否接受片切 | Whether patient accepts interproximal reduction | 1:是 (yes) 2:否 (no)",
                                                "Whether patient accepts interproximal reduction | 1:Yes 2:No"))
    other_description: Optional[str] = Field(None,
                                             description=_("其他描述", "Other description"))

    @model_validator(mode='before')
    @classmethod
    def preprocess_check_info(cls, data):
        """
        预处理检查信息，处理常见的格式问题
        Preprocess examination information, handle common format issues
        """
        # ... existing code ...

        # 处理列表字段 | Process list fields
        list_fields = ['malocclusion_type', 'main_correct_goal']
        for field in list_fields:
            if field in data and isinstance(data[field], str):
                if data[field].strip():
                    data[field] = [x.strip() for x in data[field].split(',') if x.strip()]
                else:
                    data[field] = []

        return data

    @field_validator("malocclusion_type", mode="before")
    @classmethod
    def parse_malocclusion_type_to_list(cls, v):
        """解析错颌类型字段为列表 | Parse malocclusion type field to list"""
        # 增强容错能力 | Enhance fault tolerance
        if v is None:
            return []
        if isinstance(v, str):
            if not v.strip():  # 空字符串 | Empty string
                return []
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator("main_correct_goal", mode="before")
    @classmethod
    def parse_main_correct_goal_to_list(cls, v):
        """解析主要矫治目标字段为列表 | Parse main correction goal field to list"""
        # 增强容错能力 | Enhance fault tolerance
        if v is None:
            return []
        if isinstance(v, str):
            if not v.strip():  # 空字符串 | Empty string
                return []
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    # 添加枚举字段的验证器，自动将 int 转换为 string
    # Add validator for enum fields, automatically convert int to string
    @field_validator('missing_teeth', 'primary_teeth', 'oral_health',
                     'periodontal_health', 'molar_left', 'molar_right',
                     'canines_left', 'canines_right', 'facial_type',
                     'tooth_column', 'unmovable_teeth', 'unattach_teeth',
                     'is_grow_anchorage', 'is_traction_device',
                     'is_mandible_abnormal', 'extraction_teeth',
                     'extraction_anchorage', 'is_receive_piece',
                     mode='before')
    @classmethod
    def convert_enum_to_string(cls, v):
        """
        将枚举字段的 int 值自动转换为 string
        Automatically convert int values of enum fields to string
        """
        if v is None:
            return None
        if isinstance(v, int):
            return str(v)
        return v

    @model_validator(mode='wrap')
    @classmethod
    def wrap_validator(cls, values, handler):
        """
        包装验证器，确保所有输入都能被正确处理
        Wrapper validator, ensure all inputs can be processed correctly
        """
        try:
            # 首先尝试标准验证 | Try standard validation first
            result = handler(values)
            return result
        except Exception as e:
            # 如果标准验证失败，尝试我们的自定义处理
            # If standard validation fails, try our custom processing
            try:
                processed_values = cls.preprocess_check_info(values)
                result = handler(processed_values)
                return result
            except Exception as inner_e:
                raise ValueError(_(
                    f"无法处理输入数据：{str(inner_e)}",
                    f"Unable to process input data: {str(inner_e)}"
                ))

    class Config:
        """
        配置类 | Configuration Class
        """
        # 启用额外的验证选项 | Enable extra validation options
        extra = "forbid"
        # 启用严格的类型检查 | Enable strict type checking
        validate_assignment = True


class CheckInfoTemplate(BaseCheckInfoTemplate):
    @model_validator(mode='after')
    def validate_conditional_fields(self):
        """
        验证条件必填字段
        Validate conditional required fields
        """
        # 当选择有缺失牙齿时，必须填写具体缺失牙齿位置
        # When missing teeth is selected, specific missing tooth positions must be filled
        if self.missing_teeth == "2" and not any([
            self.missing_teeth_column.left_top,
            self.missing_teeth_column.right_top,
            self.missing_teeth_column.left_bottom,
            self.missing_teeth_column.right_bottom
        ]):
            raise ValueError(_(
                "当前选择有缺失牙齿，必须填写具体缺失牙齿位置",
                "When missing teeth is selected, specific missing tooth positions must be filled"
            ))

        # 当选择有乳牙时，必须填写具体乳牙位置
        # When deciduous teeth is selected, specific deciduous tooth positions must be filled
        if self.primary_teeth == "2" and not any([
            self.primary_teeth_column.left_top,
            self.primary_teeth_column.right_top,
            self.primary_teeth_column.left_bottom,
            self.primary_teeth_column.right_bottom
        ]):
            raise ValueError(_(
                "当选择有乳牙时，必须填写具体乳牙位置",
                "When deciduous teeth is selected, specific deciduous tooth positions must be filled"
            ))

        # 当选择有不可移动牙齿时，必须填写具体不可移动牙齿位置
        # When unmovable teeth is selected, specific unmovable tooth positions must be filled
        if self.unmovable_teeth == "2" and not any([
            self.unmovable_teeth_column.left_top,
            self.unmovable_teeth_column.right_top,
            self.unmovable_teeth_column.left_bottom,
            self.unmovable_teeth_column.right_bottom
        ]):
            raise ValueError(_(
                "当前选择有不可移动牙齿，必须填写具体不可移动牙齿位置",
                "When unmovable teeth is selected, specific unmovable tooth positions must be filled"
            ))

        # 当选择有不可设计附件牙齿时，必须填写具体不可设计附件牙齿位置
        # When teeth without attachments is selected, specific positions must be filled
        if self.unattach_teeth == "2" and not any([
            self.unattach_teeth_column.left_top,
            self.unattach_teeth_column.right_top,
            self.unattach_teeth_column.left_bottom,
            self.unattach_teeth_column.right_bottom
        ]):
            raise ValueError(_(
                "当前选择有不可设计附件牙齿，必须填写具体不可设计附件牙齿位置",
                "When teeth without attachments is selected, specific positions must be filled"
            ))

        # 当选择有拔牙时，必须填写具体拔牙位置
        # When extraction is selected, specific extraction positions must be filled
        if self.extraction_teeth == "2" and not any([
            self.extraction_teeth_column.left_top,
            self.extraction_teeth_column.right_top,
            self.extraction_teeth_column.left_bottom,
            self.extraction_teeth_column.right_bottom
        ]):
            raise ValueError(_(
                "当前选择有拔牙，必须填写具体拔牙位置",
                "When extraction is selected, specific extraction positions must be filled"
            ))

        # 当主要矫治目标选择"其他"时，必须填写其他目标描述
        # When "other" is selected in main correction goals, other goal description must be filled
        if self.main_correct_goal and "5" in self.main_correct_goal:
            if not self.main_correct_goal_others or not self.main_correct_goal_others.strip():
                raise ValueError(_(
                    '当主要矫治目标中选择"5-其他"时，"其他主要矫治目标"必须填写',
                    'When "5-other" is selected in main correction goals, "other main correction goals" must be filled'
                ))

        # 当错颌类型选择"其他"时，必须填写其他描述
        # When "other" is selected in malocclusion types, other description must be filled
        if self.malocclusion_type and "13" in self.malocclusion_type:
            if not self.malocclusion_others or not self.malocclusion_others.strip():
                raise ValueError(_(
                    '当错颌类型中选择"13-其它"时，"错颌类型 - 其他"必须填写',
                    'When "13-other" is selected in malocclusion types, "malocclusion type-other" must be filled'
                ))
        return self


class FaceCheckInfoTemplate(BaseCheckInfoTemplate):
    """
    面诊用检查信息模板（大模型请严格按此结构生成数据）
    Examination information template for consultation (LLM please generate data strictly according to this structure)
    """

    # @model_validator(mode='after')
    def validate_optional_fields(self):
        """
        自定义验证器：对非必填字段进行值校验
        Custom validator: Validate values for non-required fields
        """
        errors = []

        # 校验 malocclusion_others 是否有值 | Validate if malocclusion_others has value
        if self.malocclusion_others is not None:
            # raise ValueError(f"错颌类型 - 其他内容有值")
            if self.malocclusion_type is not None:
                if isinstance(self.malocclusion_type, str):
                    data = self.malocclusion_type.strip()
                    self.malocclusion_type = [x for x in re.split(r'[;,,、]', data) if x]
                    self.malocclusion_type.append(13)
                elif isinstance(self.malocclusion_type, list):
                    self.malocclusion_type.append(13)
                else:
                    self.malocclusion_type = [13]
            else:
                self.malocclusion_type = [13]

        # 校验 main_correct_goal_others 是否有值 | Validate if main_correct_goal_others has value
        if self.main_correct_goal_others is not None:
            # raise ValueError(f"错颌类型 - 其他内容有值")
            if self.main_correct_goal is not None:
                if isinstance(self.main_correct_goal, str):
                    data = self.main_correct_goal.strip()
                    self.main_correct_goal = [x for x in re.split(r'[;,,、]', data) if x]
                    self.main_correct_goal.append(5)
                elif isinstance(self.main_correct_goal, list):
                    self.main_correct_goal.append(5)
                else:
                    self.main_correct_goal = [5]
            else:
                self.main_correct_goal = [5]

        if self.missing_teeth_column is not None:
            # self.missing_teeth_column = json.dumps(self.missing_teeth_column.model_dump())
            self.missing_teeth = 2

        if self.primary_teeth_column is not None:
            # self.primary_teeth_column = json.dumps(self.primary_teeth_column.model_dump())
            self.primary_teeth = 2

        if self.unmovable_teeth_column is not None:
            # self.unmovable_teeth_column = json.dumps(self.unmovable_teeth_column.model_dump())
            self.unmovable_teeth = 2

        if self.unattach_teeth_column is not None:
            # self.unattach_teeth_column = json.dumps(self.unattach_teeth_column.model_dump())
            self.unattach_teeth = 2

        if self.extraction_teeth_column is not None:
            # self.extraction_teeth_column = json.dumps(self.extraction_teeth_column.model_dump())
            self.extraction_teeth = 2

        # 如果有错误，抛出异常 | If there are errors, raise exception
        if errors:
            raise ValueError("; ".join(errors))

        return self
