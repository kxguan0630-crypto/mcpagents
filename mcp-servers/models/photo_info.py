from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import Optional


class PhotoPosition(BaseModel):
    """
        患者影像资料位置信息
        file_id: 获取file_id的内容
        h: 水平方向，1-左，2-右
        v: 垂直方向，1-上，2-下
        deg: 旋转角度－获取deg的内容
        score: 分数－获取score的内容
        imageType: 图片类型－获取消息内容中的imageType的信息
    """
    file_id:str = Field(None, description="file_id")
    h:int = 1
    v:int = 1
    deg:int = 0
    score:float = 0.0
    imageType: Optional[str] = Field("", description="图片类型")

    @model_validator(mode='before')
    @classmethod
    def convert_str_to_dict(cls, data):
        """核心逻辑：如果输入是字符串，自动转换为包含 file_id 的字典"""
        if isinstance(data, str):
            return {}
        elif isinstance(data,dict):
            if 'file_id' not in data:
                return {}
            result = {
                # 先设置默认值
                'h': 1,
                'v': 1,
                'deg': 0,
                'score': 0.0,
                'imageType': ''
            }
            #处理file_id可能的不同命名
            if 'fileId' in data:
                result['file_id'] = data['fileId']
            elif 'file_id' in data:
                result['file_id'] = data['file_id']

            for key in ['h','v','deg','score','imageType']:
                if key in data:
                    result[key] = data[key]
            return result
        elif data is None:
            return {}
        else:
            return {}

class BasePhotoInfoTemplate(BaseModel):
    """影像资料信息模板 - 用于收集患者影像资料

    使用场景：
    - 订单创建时提供影像资料
    - 面诊信息保存时提供影像资料
    - 更新患者影像资料时提供影像资料

    字段说明：
    - face_open：患者口外照-正面开口微笑照片
    - face_close：患者口外照-正面闭合照片
    - face_side：患者口外照-侧立照片
    - face_smile：患者口外照-侧45度微笑照片
    - mouth_upper: 上颌照片
    - mouth_lower: 下颌照片
    - mouth_cover：患者口内照-覆合覆盖照片
    - mouth_front：患者口内照-正面咬合照片
    - mouth_left: 咬合左侧位照片
    - mouth_right: 咬合右侧位照片
    - xray_front：患者X光片全颌曲面断层照片
    - xray_side：患者X光片头颅侧位定位片
    - cbct_file: CBCT文件
    """
    # 非必填字段
    face_open: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="患者口外照-正面开口微笑照片")
    face_close: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="患者口外照-正面闭合照片")
    face_side: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="患者口外照-侧立照片")
    face_smile: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="患者口外照-侧45度微笑照片")
    mouth_upper: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="上颌照片")
    mouth_lower: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="下颌照片")
    mouth_cover: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="患者口内照-覆合覆盖照片")
    mouth_front: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="患者口内照-正面咬合照片")
    mouth_left: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="咬合左侧位照片")
    mouth_right: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="咬合右侧位照片")
    xray_front: Optional[PhotoPosition] = Field(default_factory=PhotoPosition, description="患者X光片全颌曲面断层照片")
    xray_side: Optional[PhotoPosition]  = Field(default_factory=PhotoPosition, description="患者X光片头颅侧位定位片")
    cbct_file: Optional[str] = Field(None, description="CBCT文件")


    @model_validator(mode='before')
    @classmethod
    def handle_none_values(cls, data):
        """处理None值，确保模型可以正确初始化"""
        if data is None:
            return {}
        return data

class PhotoInfoTemplate(BasePhotoInfoTemplate):
    """     患者正式病例的影像资料（包含签名照片）
         字段说明：
         face_open：患者口外照-正面开口微笑照片
         face_close：患者口外照-正面闭合照片
         face_side：患者口外照-侧立照片
         face_smile：患者口外照-侧45度微笑照片
         mouth_upper: 上颌照片
         mouth_lower: 下颌照片
         mouth_cover：患者口内照-覆合覆盖照片
         mouth_front：患者口内照-正面咬合照片
         mouth_left: 咬合左侧位照片
         mouth_right: 咬合右侧位照片
         xray_front：患者X光片全颌曲面断层照片
         xray_side：患者X光片头颅侧位定位片
         cbct_file: CBCT文件
         sign_one:签名第一张照片
         sign_two:签名第二张照片
    """

    sign_one: Optional[PhotoPosition] = Field(default_factory=PhotoPosition,
                                              description="签名第一张照片（如果是正式装产品，必填）")
    sign_two: Optional[PhotoPosition] = Field(default_factory=PhotoPosition,
                                              description="签名第二张照片（如果是正式装产品，必填）")


    @model_validator(mode='before')
    @classmethod
    def handle_none_values(cls, data):
        """处理None值，确保模型可以正确初始化"""
        if data is None:
            return {}
        return data

class FacePhotoInfoTemplate(BasePhotoInfoTemplate):
    """
    面诊影像资料
    """
