from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class SubStageInfoTemplate(BaseModel):
    """申请阶段调整信息模板 - 用于收集阶段调整申请信息 / Application for Stage Adjustment Information
    使用场景 / Usage Scenarios:
    - 申请阶段调整时提供调整信息 / Provide adjustment information when applying for stage adjustment

    必填字段 / Required Fields:
    - reason: 调整原因 / Adjustment reason: 1-牙齿移动偏离原方案 (Teeth movement deviates from original plan) 2-患者做过新的修复或补牙 (Patient had new restoration or filling) 3-治疗方案改变 (Treatment plan changed) 4-治疗结束需要精细调整 (Treatment completed, needs fine adjustment) 5-患者依从性差佩戴时长不足 (Poor patient compliance, insufficient wearing time)
    - appliance: 当前矫治器贴合情况 / Current aligner fit condition: 1-矫治器贴合 (Aligner fits well), 2-矫治器不贴合 (Aligner doesn't fit well)
    - upper_step: 当前佩戴矫治器上颌步数（最小为 0，最大为 get_stage_num 返回的 total_periods）/ Current upper aligner step number (min: 0, max: total_periods from get_stage_num)
    - lower_step: 当前佩戴矫治器下颌步数（最小为 0，最大为 get_stage_num 返回的 total_periods）/ Current lower aligner step number (min: 0, max: total_periods from get_stage_num)

    可选字段 / Optional Fields:
    - remark: 设计要求备注 / Design requirement remarks


    """
    # 必填字段 / Required Fields
    reason: str = Field(...,description="调整原因 / Adjustment reason: 1-牙齿移动偏离原方案 (Teeth movement deviates from original plan) 2-患者做过新的修复或补牙 (Patient had new restoration or filling) 3-治疗方案改变 (Treatment plan changed) 4-治疗结束需要精细调整 (Treatment completed, needs fine adjustment) 5-患者依从性差佩戴时长不足 (Poor patient compliance, insufficient wearing time)")
    appliance: str = Field(...,
                           description="当前矫治器贴合情况 / Current aligner fit condition: 1-矫治器贴合 (Aligner fits well), 2-矫治器不贴合 (Aligner doesn't fit well)")
    upper_step: str = Field(..., description="当前佩戴矫治器上颌步数 / Current upper aligner step number")
    lower_step: str = Field(..., description="当前佩戴矫治器下颌步数 / Current lower aligner step number")

    # 非必填字段 / Optional Fields
    remark: Optional[str] = Field(None, description="设计要求备注 / Design requirement remarks")

    @field_validator('upper_step', 'lower_step', mode='before')
    @classmethod
    def convert_to_string(cls, v):
        """自动将 int 转换为 string"""
        if isinstance(v, int):
            return str(v)
        return v

    @field_validator('reason', 'appliance', mode='before')
    @classmethod
    def convert_enum_to_string(cls, v):
        """自动将 int 转换为 string"""
        if isinstance(v, int):
            return str(v)
        return v