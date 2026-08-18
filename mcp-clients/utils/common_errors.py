def _extract_user_friendly_error(self, error_message: str, we_lang: str = "zh-CN") -> str:
    """从原始错误信息中提取对用户友好的提示"""
    import re
    import json

    # 尝试解析 JSON 格式的错误信息
    try:
        error_data = json.loads(error_message)
        if isinstance(error_data, dict):
            if 'details' in error_data:
                error_message = error_data['details']
            elif 'message' in error_data:
                error_message = error_data.get('message', error_message)
    except (json.JSONDecodeError, TypeError):
        pass

    # 1. 检测 Pydantic 类型错误（string_type, integer_type 等）
    type_error_matches = re.findall(r'(\w+)\s+Input should be a valid (\w+) \[type=(\w+)_type', error_message)

    if type_error_matches:
        invalid_fields = list(set([match[0] for match in type_error_matches]))

        if we_lang == "en-US":
            return f"Invalid data format for fields: {', '.join(invalid_fields)}. Please check the data types."
        else:
            return f"字段数据格式不正确：{', '.join(invalid_fields)}。请检查数据类型。"

    # 2. 检测字段缺失错误（Field required）
    field_required_matches = re.findall(r'(\w+)\s+Field required \[type=missing', error_message)

    if field_required_matches:
        missing_fields = list(set(field_required_matches))

        if we_lang == "en-US":
            return f"Missing required fields: {', '.join(missing_fields)}. Please provide complete information."
        else:
            return f"缺少必填字段：{', '.join(missing_fields)}。请补充完整信息。"

    # 3. 查找 "Value error," 后面的中文或英文描述
    value_error_matches = re.findall(r'Value error,\s*([^\n\[]+)', error_message)

    if value_error_matches:
        error_detail = value_error_matches[-1].strip()
        error_detail = re.sub(r'^[\s\n]+', '', error_detail).strip()
        return error_detail

    # 4. 尝试提取其他常见错误模式
    # 匹配 "N validation errors for XXX" 的总结信息
    summary_match = re.search(r'(\d+) validation errors? for (\w+)', error_message)
    if summary_match:
        error_count = summary_match.group(1)
        model_name = summary_match.group(2)

        if we_lang == "en-US":
            return f"Validation failed for {model_name}. {error_count} error(s) found. Please check your input."
        else:
            return f"{model_name} 验证失败，共发现 {error_count} 个错误。请检查输入信息。"

    # 5. 返回默认错误信息
    default_messages = {
        "zh-CN": "操作失败，请检查您填写的信息是否完整和正确。",
        "en-US": "Operation failed. Please check that your information is complete and correct."
    }

    return default_messages.get(we_lang, default_messages["zh-CN"])
