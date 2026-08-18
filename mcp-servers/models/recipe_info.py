from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Optional, List
from models.check_info import ToothPosition
from typing_extensions import Annotated
import re
from models.validators import _


class RecipeInfoTemplate(BaseModel):
    """处方信息模板 - 用于收集患者矫治处方信息
    Prescription Information Template - Used to collect patient orthodontic prescription information

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

    使用场景 / Usage Scenarios:
    - 订单创建时提供处方信息 / Provide prescription when creating order
    - 阶段调整时提供处方信息 / Provide prescription during stage adjustment
    - 更新处方信息时提供处方信息 / Update prescription information

    字段说明 / Field Descriptions:
    - 带有 "|" 符号的字段为枚举类型，冒号后为可选值 / Fields with "|" are enum types, values after colon
    - 带有 "以下牙齿" 字样的字段需要配合其对应的开关字段使用 / Fields with "teeth below" need corresponding switch fields
    - 所有牙齿位置字段使用 ToothPosition 结构 / All tooth position fields use ToothPosition structure

    条件必填字段 / Conditional Required Fields:
    - occlusal_guide_setting=2 时，occlusal_guide_setting_column 必填 / When occlusal_guide_setting=2, occlusal_guide_setting_column is required
    - space=2 时，space_reserved_remark 必填 / When space=2, space_reserved_remark is required
    - crowd!=none 时，crowding_upper 和 crowding_lower 必填 / When crowd!=none, crowding_upper and crowding_lower are required
    - adjust_type 包含"60"时，adjust_other 必填 / When adjust_type contains "60", adjust_other is required
    - over_teeth=1 时，over_teeth_other 必填 / When over_teeth=1, over_teeth_other is required
    - midline_upper 在("2","3")时，midline_upper_length 必填 / When midline_upper in ("2","3"), midline_upper_length is required
    - midline_lower 在("2","3")时，midline_lower_length 必填 / When midline_lower in ("2","3"), midline_lower_length is required
    """
    occlusal_guide_setting: Optional[str] = Field(None, description=_("咬合导板设置|1:无 2:放置位置",
                                                                      "Occlusal guide setting|1:None 2:Placement position"))
    occlusal_guide_setting_column: Optional[ToothPosition] = Field(default_factory=ToothPosition,
                                                                   description=_("咬合导板设置 - 放置位置",
                                                                                 "Occlusal guide setting - Placement position"))
    spee_curve: Optional[str] = Field(None, description=_("Spee 曲线|1-保持 2-改善 3-完全整平",
                                                          "Spee curve|1-Maintain 2-Improve 3-Level completely"))
    sagittal_left: Optional[str] = Field(None,
                                         description=_(
                                             "矢状向关系左侧:1-维持 2-仅改善尖牙关系 3-改善尖牙和磨牙关系 4-调整到中性",
                                             "Sagittal relationship left:1-Maintain 2-Improve canine only 3-Improve canine and molar 4-Adjust to neutral"))
    sagittal_right: Optional[str] = Field(None,
                                          description=_(
                                              "矢状向关系右侧:1-维持 2-仅改善尖牙关系 3-改善尖牙和磨牙关系 4-调整到中性",
                                              "Sagittal relationship right:1-Maintain 2-Improve canine only 3-Improve canine and molar 4-Adjust to neutral"))
    cover_relation: Optional[str] = Field(None, description=_("覆盖关系:1-维持 2-改善",
                                                              "Cover relationship:1-Maintain 2-Improve"))
    overbite: Optional[str] = Field(None,
                                    description=_(
                                        "覆颌关系|1-维持 5-压低上前牙改善 6-压低下前牙改善 7-伸长上前牙改善 8-伸长下前牙改善",
                                        "Overbite relationship|1-Maintain 5-Intrude upper anterior 6-Intrude lower anterior 7-Extrude upper anterior 8-Extrude lower anterior"))
    anterior_crossbite: Optional[str] = Field(None, description=_("前牙反颌/对刃|1-维持 2-纠正",
                                                                  "Anterior crossbite/edge-to-edge|1-Maintain 2-Correct"))
    facial_method: Optional[str] = Field(None,
                                         description=_("面型:1-维持 2-改善", "Facial profile:1-Maintain 2-Improve"))
    midline_upper: Optional[str] = Field(None,
                                         description=_(
                                             "中线位置 - 上中线:1-维持 2-向患者左侧移动 3-向患者右侧移动 4-根据方案确定",
                                             "Midline position - Upper midline:1-Maintain 2-Move to patient's left 3-Move to patient's right 4-Determine by plan"))
    crowd: Optional[str] = Field(None, description=_("拥挤 是否需要治疗 如果不需要治疗，输入 none",
                                                     "Crowding - Need treatment? If no treatment needed, input none"))
    crowding_upper: Annotated[
        Optional[List[str]],
        Field(description=_("上颌拥挤，可多选，用，隔开:1-扩弓 2-唇倾 3-邻面去釉 4-磨牙远移 5-拔牙 none-不需要治疗",
                            "Upper crowding, multiple choice, separate with comma:1-Expansion 2-Labial inclination 3-IPR 4-Molar distalization 5-Extraction none-No treatment"))
    ] = None
    crowding_lower: Annotated[
        Optional[List[str]],
        Field(description=_("下颌拥挤，可多选，用，隔开:1-扩弓 2-唇倾 3-邻面去釉 4-磨牙远移 5-拔牙 none-不需要治疗",
                            "Lower crowding, multiple choice, separate with comma:1-Expansion 2-Labial inclination 3-IPR 4-Molar distalization 5-Extraction none-No treatment"))
    ] = None
    locking: Optional[str] = Field(None, description=_("后牙反颌或锁颌是否需要矫治|1-是 2-否",
                                                       "Posterior crossbite/crossbite correction needed|1-Yes 2-No"))
    over_teeth: Optional[str] = Field(None, description=_("是否过矫正|1:是 2:否", "Over-correction|1:Yes 2:No"))
    space: Optional[str] = Field(None, description=_("间隙|1:全部关闭 2:间隙保留", "Space|1:Close all 2:Reserve space"))
    adjust_type: Annotated[
        Optional[List[str]],
        Field(description=_("矫正类型:10-邻面去釉 20-磨牙远移 30-扩弓 40-拔牙 50-根据 3D 方案 60-其它",
                            "Correction type:10-IPR 20-Molar distalization 30-Expansion 40-Extraction 50-According to 3D plan 60-Other"))
    ] = None
    midline_lower: Optional[str] = Field(None,
                                         description=_(
                                             "中线位置 - 下中线位置:1-维持 2-向患者左侧移动 3-向患者右侧移动 4-根据方案确定",
                                             "Midline position - Lower midline:1-Maintain 2-Move to patient's left 3-Move to patient's right 4-Determine by plan"))
    midline_upper_length: Optional[str] = Field(None, description=_("中线位置 - 上中线移动距离",
                                                                    "Midline position - Upper midline movement distance"))
    midline_lower_length: Optional[str] = Field(None, description=_("中线位置 - 下中线移动距离",
                                                                    "Midline position - Lower midline movement distance"))
    space_reserved_remark: Optional[str] = Field(None, description=_("间隙保留要求", "Space reservation requirements"))
    over_teeth_other: Optional[str] = Field(None, description=_("过矫正的特殊需求",
                                                                "Special requirements for over-correction"))
    adjust_other: Optional[str] = Field(None, description=_("矫正类型为其他，输入的内容",
                                                            "Content when correction type is other"))
    target: Optional[str] = Field(None,
                                  description=_("矫治目标及特殊说明", "Treatment objectives and special instructions"))

    @model_validator(mode='before')
    @classmethod
    def handle_none_values(cls, data):
        """处理 None 值，确保模型可以正确初始化 / Handle None values to ensure model can be initialized correctly"""
        if data is None:
            return {}
        return data

    @model_validator(mode='before')
    @classmethod
    def preprocess_recipe_info(cls, data):
        """预处理处方信息，处理常见的格式问题 / Preprocess prescription information, handle common format issues"""
        if not isinstance(data, dict):
            return data

        # 处理牙齿位置字段 / Process tooth position fields
        tooth_fields = [
            'occlusal_guide_setting_column',
        ]

        for field in tooth_fields:
            if field in data and isinstance(data[field], str):
                if data[field].strip():
                    # 将字符串转换为 ToothPosition 期望的格式 / Convert string to ToothPosition expected format
                    tooth_nums = []
                    separators = r'[;,，、\s]+'
                    parts = re.split(separators, data[field])
                    for part in parts:
                        part = part.strip()
                        if part and part.isdigit():
                            tooth_nums.append(int(part))

                    # 构造 ToothPosition 格式 / Construct ToothPosition format
                    tooth_position = {
                        'left_top': [],
                        'right_top': [],
                        'left_bottom': [],
                        'right_bottom': []
                    }

                    for num in tooth_nums:
                        if (11 <= num <= 18) or (51 <= num <= 55):
                            tooth_position['left_top'].append(num)
                        elif (21 <= num <= 28) or (61 <= num <= 65):
                            tooth_position['right_top'].append(num)
                        elif (31 <= num <= 38) or (71 <= num <= 75):
                            tooth_position['left_bottom'].append(num)
                        elif (41 <= num <= 48) or (81 <= num <= 85):
                            tooth_position['right_bottom'].append(num)

                    data[field] = tooth_position
                else:
                    # 空字符串转换为空的 ToothPosition / Convert empty string to empty ToothPosition
                    data[field] = {
                        'left_top': [],
                        'right_top': [],
                        'left_bottom': [],
                        'right_bottom': []
                    }

        # 处理列表字段 / Process list fields
        list_fields = ['crowding_upper', 'crowding_lower', 'adjust_type']
        for field in list_fields:
            if field in data and isinstance(data[field], str):
                if data[field].strip():
                    data[field] = [x.strip() for x in data[field].split(',') if x.strip()]
                else:
                    data[field] = []

        return data

    @field_validator("crowding_upper", mode="before")
    @classmethod
    def parse_crowding_upper_to_list(cls, v):
        """解析上颌拥挤字段为列表 / Parse crowding_upper field to list"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")] if "," in v else [v.strip()]
        return v

    @field_validator("crowding_lower", mode="before")
    @classmethod
    def parse_crowding_lower_to_list(cls, v):
        """解析下颌拥挤字段为列表 / Parse crowding_lower field to list"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")] if "," in v else [v.strip()]
        return v

    @field_validator("adjust_type", mode="before")
    @classmethod
    def parse_adjust_type_to_list(cls, v):
        """解析矫正类型字段为列表 / Parse adjust_type field to list"""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")] if "," in v else [v.strip()]
        return v

    @model_validator(mode='after')
    def validate_conditional_fields(self):
        """验证条件必填字段 / Validate conditional required fields"""
        if self.occlusal_guide_setting == "2" and not any([
            self.occlusal_guide_setting_column.left_top,
            self.occlusal_guide_setting_column.left_bottom,
            self.occlusal_guide_setting_column.right_top,
            self.occlusal_guide_setting_column.right_bottom
        ]):
            raise ValueError(_(
                "当选择放置咬合导板时，必须填写具体放置位置",
                "When selecting placement of occlusal guide, specific placement position must be filled"
            ))

        # 当选择保留间隙时，必须填写间隙保留要求
        # When selecting space reservation, space reservation requirements must be filled
        if self.space == "2" and (not self.space_reserved_remark or not self.space_reserved_remark.strip()):
            raise ValueError(_(
                "当选择保留间隙时，必须填写间隙保留要求",
                "When selecting space reservation, space reservation requirements must be filled"
            ))

        # 当选择需要治疗拥挤时，必须填写上下颌拥挤治疗方案
        # When selecting crowding treatment, upper and lower crowding treatment plans must be filled
        if self.crowd and self.crowd != "none":
            if not self.crowding_upper:
                raise ValueError(_(
                    "当选择需要治疗拥挤时，必须填写上颌 crowded_upper",
                    "When selecting crowding treatment, upper crowding treatment (crowding_upper) must be filled"
                ))
            if not self.crowding_lower:
                raise ValueError(_(
                    "当选择需要治疗拥挤时，必须填写下颌 crowded_lower",
                    "When selecting crowding treatment, lower crowding treatment (crowding_lower) must be filled"
                ))

        # 当矫正类型选择其他时，必须填写具体内容
        # When correction type is "Other", specific content must be filled
        if self.adjust_type and "60" in self.adjust_type:
            if not self.adjust_other or not self.adjust_other.strip():
                raise ValueError(_(
                    '当矫正类型选择"60-其它"时，必须填写具体矫正内容',
                    'When correction type "60-Other" is selected, specific correction content must be filled'
                ))

        # 当选择过矫正时，必须填写特殊需求
        # When selecting over-correction, special requirements must be filled
        if self.over_teeth == "1" and (not self.over_teeth_other or not self.over_teeth_other.strip()):
            raise ValueError(_(
                "当选择过矫正时，必须填写过矫正特殊需求",
                "When selecting over-correction, special requirements for over-correction must be filled"
            ))

        # 当选择移动上中线时，必须填写移动距离
        # When selecting upper midline movement, movement distance must be filled
        if self.midline_upper in ("2", "3") and (
                not self.midline_upper_length or not self.midline_upper_length.strip()):
            raise ValueError(_(
                "当选择移动上中线时，必须填写上中线移动距离",
                "When selecting upper midline movement, upper midline movement distance must be filled"
            ))

        # 当选择移动下中线时，必须填写移动距离
        # When selecting lower midline movement, movement distance must be filled
        if self.midline_lower in ("2", "3") and (
                not self.midline_lower_length or not self.midline_lower_length.strip()):
            raise ValueError(_(
                "当选择移动下中线时，必须填写下中线移动距离",
                "When selecting lower midline movement, lower midline movement distance must be filled"
            ))

        return self

    class Config:
        # 启用额外的验证选项 / Enable additional validation options
        extra = "forbid"
        # 启用严格的类型检查 / Enable strict type checking
        validate_assignment = True