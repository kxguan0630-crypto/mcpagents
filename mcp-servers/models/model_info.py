from pydantic import BaseModel, Field, model_validator, validator
from typing import Optional


class BaseModelInfoTemplate(BaseModel):
    """模型文件数据模板 - 用于收集模型文件信息

    使用场景：
    - 订单创建时提供模型信息
    - 面诊信息保存时提供模型信息
    -　更新模型时提供模型信息

    字段说明：
    - mouth_upper: 上颌模型文件
    - mouth_lower: 下颌模型文件
    - mouth_left: 左侧咬合文件
    - mouth_right: 右侧咬合文件
    - other_file: 其它类型文件
    """
    # 非必填字段
    mouth_upper: Optional[str] = Field(None, description="上颌模型文件")
    mouth_lower: Optional[str] = Field(None, description="下颌模型文件")
    mouth_right: Optional[str] = Field(None, description="右侧咬合文件")
    mouth_left: Optional[str] = Field(None, description="左侧咬合文件")
    other_file: Optional[str] = Field(None, description="其它类型文件")

    @validator('*', pre=True)
    def convert_dict_to_str(cls, v):
        if isinstance(v, dict):
            return v.get('file_id') or str(v)
        return v

    @model_validator(mode='before')
    @classmethod
    def handle_none_values(cls, data):
        """处理None值，确保模型可以正确初始化"""
        if data is None:
            return {}
        return data

class ModelInfoTemplate(BaseModelInfoTemplate):
    """模型文件"""


class FaceModelInfoTemplate(BaseModelInfoTemplate):
    """面诊模型文件"""
