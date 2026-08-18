# utils/exceptions.py
class OrthodonticServiceError(Exception):
    """正畸服务基础异常类"""
    def __init__(self, message: str, code: int = 50000):
        self.message = message
        self.code = code
        super().__init__(self.message)

class ValidationError(OrthodonticServiceError):
    """数据验证异常"""
    def __init__(self, message: str):
        super().__init__(message, 30000)

class ExternalAPIError(OrthodonticServiceError):
    """外部API调用异常"""
    def __init__(self, message: str):
        super().__init__(message, 40000)
