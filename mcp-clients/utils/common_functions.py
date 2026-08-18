def _summarize_tool_result(result_text: str, tool_name: str, we_lang="zh-CN") -> str:
    """
    根据工具返回结果生成友好的摘要提示

    Args:
        result_text: 工具返回的 JSON 字符串或文本
        tool_name: 工具名称
        we_lang: 语言偏好，zh-CN(中文) 或 en-US(英文)

    Returns:
        友好的用户提示信息
    """
    try:
        import json
        data = json.loads(result_text)

        # ==================== 面诊管理类 ====================

        if tool_name == "case_face_list":
            messages = {
                "zh-CN": f"📋 面诊列表\n共有 {len(data)} 个面诊",
                "en-US": f"📋 Face Consultation List\nTotal of {len(data)} consultations"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "case_face_detail":
            messages = {
                "zh-CN": "✅ 面诊详情信息已查询",
                "en-US": "✅ Face consultation details retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "save_case_face":
            messages = {
                "zh-CN": "✅ 面诊信息已更新",
                "en-US": "✅ Face consultation information updated"
            }
            return messages.get(we_lang, messages["zh-CN"])


        # ==================== 保持器订单类 ====================

        elif tool_name == "save_retainer_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": "❌ 保持器订单创建失败！\n" if (code is not None and code != "") else "✅ 保持器订单创建成功！\n",
                "en-US": "❌ Failed to create retainer order!\n" if (
                            code is not None and code != "") else "✅ Retainer order created successfully!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])


        elif tool_name == "get_retainer_list":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 获取保持器订单列表失败！\n" if (
                            code is not None and code != "") else f"📦 获取保持器订单列表成功！\n",
                "en-US": f"❌ Failed to get retainer order list!\n" if (
                            code is not None and code != "") else f"📦 Retainer order list retrieved successfully!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_retainer_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 保持器订单查询失败！\n" if (
                            code is not None and code != "") else f"✅ 获取保持器订单详情成功！\n",
                "en-US": f"❌ Failed to query retainer order!\n" if (
                            code is not None and code != "") else f"✅ Retainer order details retrieved successfully!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])

        # ==================== 病例管理类 ====================

        elif tool_name == "case_add":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 病例创建失败！\n" if (code is not None and code != "") else f"✅ 病例创建成功！\n",
                "en-US": f"❌ Failed to create case!\n" if (
                            code is not None and code != "") else f"✅ Case created successfully!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])


        elif tool_name == "get_patients_by_name_and_phone":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 患者信息查询失败！\n" if (code is not None and code != "") else "📦 获取患者列表成功！\n",
                "en-US": f"❌ Failed to query patient information!\n" if (
                            code is not None and code != "") else "📦 Patient list retrieved successfully!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_patient_case_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 病例查询失败！\n" if (code is not None and code != "") else "✅ 病例查询成功！\n",
                "en-US": f"❌ Failed to query case!\n" if (
                            code is not None and code != "") else "✅ Case queried successfully!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])

        # ==================== 阶段调整类 ====================

        elif tool_name == "get_stage_num":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 阶段调整信息查询失败！\n" if (code is not None and code != "") else f"✅ 阶段调整信息已查询",
                "en-US": f"❌ Failed to query stage adjustment information!\n" if (
                            code is not None and code != "") else f"✅ Stage adjustment information queried"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "submit_stage_adjustment":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 阶段调整信息保存失败！\n" if (
                            code is not None and code != "") else "✅ 阶段调整申请信息已保存",
                "en-US": f"❌ Failed to save stage adjustment information!\n" if (
                            code is not None and code != "") else "✅ Stage adjustment application saved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        # ==================== 补发矫治器类 ====================

        elif tool_name == "save_appliance_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 补发矫治器订单保存失败！\n" if (
                            code is not None and code != "") else f"✅ 补发矫治器订单已保存",
                "en-US": f"❌ Failed to save appliance order!\n" if (
                            code is not None and code != "") else f"✅ Appliance order saved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_appliance_list":
            code = data.get("code", "")
            if code is not None and code != "":
                messages = {
                    "zh-CN": f"❌ 补发矫治器订单查询失败！\n",
                    "en-US": f"❌ Failed to query appliance orders!\n"
                }
                return messages.get(we_lang, messages["zh-CN"])
            messages = {
                "zh-CN": f"📦 获取补发矫治器订单列表成功！\n",
                "en-US": f"📦 Appliance order list retrieved successfully!\nTotal of {len(data)} orders"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_appliance_info":
            code = data.get("code", "")
            if code is not None and code != "":
                messages = {
                    "zh-CN": f"❌ 补发矫治器订单详情查询失败！\n",
                    "en-US": f"❌ Failed to query appliance order details!\n"
                }
                return messages.get(we_lang, messages["zh-CN"])
            messages = {
                "zh-CN": "✅ 补发矫治器订单详情已查询",
                "en-US": "✅ Appliance order details queried"
            }
            return messages.get(we_lang, messages["zh-CN"])

        # ==================== 影像处理类 ====================

        elif tool_name == "image_process":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 智能影像识别失败！\n" if (code is not None and code != "") else "✅ 智能影像识别已完成",
                "en-US": f"❌ Smart image recognition failed!\n" if (
                            code is not None and code != "") else "✅ Smart image recognition completed"
            }
            return messages.get(we_lang, messages["zh-CN"])

        # ==================== 产品与权益管理 ====================

        elif tool_name == "get_product_list":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 产品列表查询失败！\n" if (code is not None and code != "") else "✨ 已获取到产品列表",
                "en-US": f"❌ Failed to query product list!\n" if (
                            code is not None and code != "") else "✨ Product list retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_equity_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 产品权益查询失败！\n" if (code is not None and code != "") else "✅ 已查询到产品权益信息",
                "en-US": f"❌ Failed to query product equity!\n" if (
                            code is not None and code != "") else "✅ Product equity information retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])


        # ==================== 订单管理 - 查询类 ====================

        elif tool_name == "check_order_by_case_code":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 病例关联订单查询失败！\n" if (
                            code is not None and code != "") else f"✅ 已完成该病例关联订单查询",
                "en-US": f"❌ Failed to query case-related orders!\n" if (
                            code is not None and code != "") else f"✅ Case-related order query completed"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_order_list":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 订单列表查询失败！\n" if (code is not None and code != "") else f"📦 已获取到订单列表",
                "en-US": f"❌ Failed to query order list!\n" if (
                            code is not None and code != "") else f"📦 Order list retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "order_detail":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 订单详情查询失败！\n" if (code is not None and code != "") else "✅ 已查询到订单详情",
                "en-US": f"❌ Failed to query order details!\n" if (
                            code is not None and code != "") else "✅ Order details queried"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_order_remain_periods":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 订单剩余期数查询失败！\n" if (
                            code is not None and code != "") else f"✅ 已获取到订单剩余期数信息",
                "en-US": f"❌ Failed to query order remaining periods!\n" if (
                            code is not None and code != "") else f"✅ Order remaining periods information retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_batch_product_list":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 批次列表查询失败！\n" if (code is not None and code != "") else "✨ 已获取到批次列表",
                "en-US": f"❌ Failed to query batch list!\n" if (
                            code is not None and code != "") else "✨ Batch list retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_pay_list":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 批次支付列表查询失败！\n" if (code is not None and code != "") else "✨ 已获取到支付列表",
                "en-US": f"❌ Failed to query payment list!\n" if (
                            code is not None and code != "") else "✨ Payment list retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "get_recipe_list":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 批次处方列表查询失败！\n" if (code is not None and code != "") else "✨ 已获取到处方列表",
                "en-US": f"❌ Failed to query recipe list!\n" if (
                            code is not None and code != "") else "✨ Recipe list retrieved"
            }
            return messages.get(we_lang, messages["zh-CN"])

        # ==================== 订单管理 - 操作类 ====================

        elif tool_name == "case_order_add":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 订单创建失败！\n" if (code is not None and code != "") else "✅ 订单创建成功！\n",
                "en-US": f"❌ Failed to create order!\n" if (
                            code is not None and code != "") else "✅ Order created successfully!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "order_apply_delivery":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 订单发货申请失败！\n" if (code is not None and code != "") else "✅ 订单发货申请已提交！\n",
                "en-US": f"❌ Failed to apply for order delivery!\n" if (
                            code is not None and code != "") else "✅ Order delivery application submitted!\n"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "save_photo_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 影像资料更新失败！\n" if (code is not None and code != "") else "✅ 影像资料已更新",
                "en-US": f"❌ Failed to update photo information!\n" if (
                            code is not None and code != "") else "✅ Photo information updated"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "save_check_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 临床诊断信息更新失败！\n" if (code is not None and code != "") else "✅ 临床诊断信息已更新",
                "en-US": f"❌ Failed to update check information!\n" if (
                            code is not None and code != "") else "✅ Check information updated"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "save_model_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 模型信息更新失败！\n" if (code is not None and code != "") else "✅ 模型信息已更新",
                "en-US": f"❌ Failed to update model information!\n" if (
                            code is not None and code != "") else "✅ Model information updated"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "save_recipe_info":
            code = data.get("code", "")
            messages = {
                "zh-CN": f"❌ 处方信息更新失败！\n" if (code is not None and code != "") else "✅ 处方信息已更新",
                "en-US": f"❌ Failed to update recipe information!\n" if (
                            code is not None and code != "") else "✅ Recipe information updated"
            }
            return messages.get(we_lang, messages["zh-CN"])

        elif tool_name == "execute_command_open_ksapp":
            button = data.get("button", "")
            if button:
                button = True
            else:
                button = False

            messages = {
                "zh-CN": {
                    True: f"✅ 已准备启动口扫软件\n请点击按钮继续操作",
                    False: "❌ 启动失败，请稍后重试"
                },
                "en-US": {
                    True: f"✅ Ready to start intraoral scanner software\nPlease click the button to continue",
                    False: "❌ Failed to start, please try again later"
                }
            }
            lang_messages = messages.get(we_lang, messages["zh-CN"])
            return lang_messages.get(bool(button), lang_messages[False])

        # ==================== 默认处理 ====================

        else:
            code = data.get("code", "")
            if code is not None and code != "":
                messages = {
                    "zh-CN": f"❌ {tool_name} 操作失败！\n",
                    "en-US": f"❌ {tool_name} operation failed!\n"
                }
                return messages.get(we_lang, messages["zh-CN"])

            messages = {
                "zh-CN": "✨ 操作已完成",
                "en-US": "✨ Operation completed"
            }
            return messages.get(we_lang, messages["zh-CN"])

    except json.JSONDecodeError:
        result_lower = result_text.lower()
        if any(keyword in result_lower for keyword in ["错误", "error", "失败", "fail"]):
            clean_text = result_text.split(":")[0].strip() if ":" in result_text else result_text

            messages = {
                "zh-CN": f"❌ {clean_text[:100]}",
                "en-US": f"❌ {clean_text[:100]}"
            }
            return messages.get(we_lang, messages["zh-CN"])
        elif result_text.strip():
            messages = {
                "zh-CN": f"✅ {result_text[:100]}",
                "en-US": f"✅ {result_text[:100]}"
            }
            return messages.get(we_lang, messages["zh-CN"])
        else:
            messages = {
                "zh-CN": "✅ 操作已完成",
                "en-US": "✅ Operation completed"
            }
            return messages.get(we_lang, messages["zh-CN"])

    except Exception as e:
        messages = {
            "zh-CN": "✅ 操作已完成",
            "en-US": "✅ Operation completed"
        }
        return messages.get(we_lang, messages["zh-CN"])


def _get_friendly_name(tool_name: str, we_lang: str = "zh-CN") -> str:
    """
    将内部工具函数名映射为用户友好的名称。
    策略：优先精确匹配字典，其次根据前缀/关键词智能推断。

    Args:
        tool_name: 工具名称
        we_lang: 语言偏好，zh-CN(中文) 或 en-US(英文)

    Returns:
        友好的工具名称
    """
    # 1. 精确映射表 (覆盖所有已知工具)
    friendly_map_zh = {
        # --- 📋 病例管理类 ---
        "case_add": "创建新病例",
        "get_patients_by_name_and_phone": "查询患者信息",
        "get_patient_case_info": "获取病例详情",

        # --- 📦 订单管理类 ---
        "case_order_add": "创建新订单",
        "check_order_by_case_code": "核查病例是否有关联订单",
        "get_order_list": "查询订单列表",
        "order_detail": "查看订单详情",
        "get_order_remain_periods": "查询订单剩余期数信息",
        "order_apply_delivery": "申请发货",
        "get_batch_product_list": "查询发货批次和产品清单",
        "get_pay_list": "查询支付记录",
        "get_recipe_list": "查询处方列表",
        "save_photo_info": "更新影像资料",
        "save_check_info": "更新诊断信息",
        "save_model_info": "更新模型数据",
        "save_recipe_info": "更新处方信息",
        "execute_command_open_ksapp": "启动口扫仪",
        "get_main_order_info": "查询主订单信息",
        "check_recipe_editable_status": "核查处方是否可编辑",
        "check_order_editable_status": "核查订单是否可编辑",

        # --- ✨ 产品权益类 ---
        "get_product_list": "查询产品列表",
        "get_equity_info": "查询权益详情",

        # --- 📸 影像处理类 ---
        "image_process": "智能影像识别",

        # --- 🔄 阶段调整类 ---
        "get_stage_num": "查询阶段调整剩余次数等相关信息",
        "submit_stage_adjustment": "申请阶段调整",

        # --- 🔧 补发矫治器类 ---
        "save_appliance_info": "登记补发矫治器申请",
        "get_appliance_list": "查询补发补发矫治器列表",
        "get_appliance_info": "查询补发矫治器订单信息",

        # --- 😊 面诊管理类 ---
        "get_case_face_list": "查询面诊信息列表",
        "get_case_face_detail": "查询面诊详情",
        "save_case_face": "保存面诊信息",

        # --- 🦷 保持器订单类 ---
        "save_retainer_info": "创建保持器订单",
        "get_retainer_list": "查询保持器列表",
        "get_retainer_info": "查询保持器详情"
    }

    friendly_map_en = {
        # --- 📋 Case Management ---
        "case_add": "Create New Case",
        "get_patients_by_name_and_phone": "Query Patient Information",
        "get_patient_case_info": "Get Case Details",

        # --- 📦 Order Management ---
        "case_order_add": "Create New Order",
        "check_order_by_case_code": "Check if Case Has Related Orders",
        "get_order_list": "Query Order List",
        "order_detail": "View Order Details",
        "get_order_remain_periods": "Query Order Remaining Periods",
        "order_apply_delivery": "Apply for Delivery",
        "get_batch_product_list": "Query Batch and Product List",
        "get_pay_list": "Query Payment Records",
        "get_recipe_list": "Query Recipe List",
        "save_photo_info": "Update Photo Information",
        "save_check_info": "Update Check Information",
        "save_model_info": "Update Model Information",
        "save_recipe_info": "Update Recipe Information",
        "execute_command_open_ksapp": "Start Intraoral Scanner",
        "get_main_order_info": "Query Main Order Information",
        "check_recipe_editable_status": "Check if Recipe Is Editable",
        "check_order_editable_status": "Check if Order Is Editable",

        # --- ✨ Product & Equity ---
        "get_product_list": "Query Product List",
        "get_equity_info": "Query Equity Details",

        # --- 📸 Image Processing ---
        "image_process": "Smart Image Recognition",

        # --- 🔄 Stage Adjustment ---
        "get_stage_num": "Query Stage Adjustment Information",
        "submit_stage_adjustment": "Apply for Stage Adjustment",

        # --- 🔧 Appliance Reissue ---
        "save_appliance_info": "Register Appliance Reissue Application",
        "get_appliance_list": "Query Appliance Reissue List",
        "get_appliance_info": "Query Appliance Order Details",

        # --- 😊 Face Consultation ---
        "get_case_face_list": "Query Face Consultation List",
        "get_case_face_detail": "Query Face Consultation Details",
        "save_case_face": "Save Face Consultation Information",

        # --- 🦷 Retainer Order ---
        "save_retainer_info": "Create Retainer Order",
        "get_retainer_list": "Query Retainer List",
        "get_retainer_info": "Query Retainer Details"
    }

    # 根据语言选择映射表
    friendly_map = friendly_map_en if (we_lang and we_lang.lower().startswith('en')) else friendly_map_zh

    # 如果存在精确匹配，直接返回
    if tool_name in friendly_map:
        return friendly_map[tool_name]

    # 2. 智能兜底逻辑 (防止未来新增工具未配置时显示英文函数名)
    name_lower = tool_name.lower()

    # 按动作类型推断
    if name_lower.startswith("get_") or name_lower.startswith("check_") or name_lower.startswith("query_"):
        action = "Query" if ("list" in name_lower or "info" in name_lower) else "Check"
        # 尝试提取核心业务词 (简单处理：去掉下划线和前缀)
        core_name = tool_name.replace("get_", "").replace("check_", "").replace("_", " ")
        return f"{action} {core_name}"

    elif name_lower.startswith("save_") or name_lower.startswith("add_") or name_lower.startswith(
            "create_") or name_lower.startswith("submit_"):
        return "Save/Submit Information" if (we_lang and we_lang.lower().startswith('en')) else "保存/提交信息"

    elif name_lower.startswith("delete_") or name_lower.startswith("remove_"):
        return "Delete Operation" if (we_lang and we_lang.lower().startswith('en')) else "删除操作"

    elif "image" in name_lower or "photo" in name_lower:
        return "Image Processing" if (we_lang and we_lang.lower().startswith('en')) else "影像处理"

    elif "order" in name_lower:
        return "Order Related Operation" if (we_lang and we_lang.lower().startswith('en')) else "订单相关操作"

    elif "case" in name_lower:
        return "Case Related Operation" if (we_lang and we_lang.lower().startswith('en')) else "病例相关操作"

    elif "execute" in name_lower or "open" in name_lower:
        return "Execute System Command" if (we_lang and we_lang.lower().startswith('en')) else "执行系统命令"

    # 3. 最终兜底：将 snake_case 转换为可读文本
    return tool_name.replace("_", " ").title()
