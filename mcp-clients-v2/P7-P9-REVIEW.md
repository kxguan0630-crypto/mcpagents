# P7 / P8 / P9 自审报告

## P7 Runtime 工程化

- Tool metadata 统一描述 `visibility / display_name / category`。
- Workflow fact tools 标记为 `visibility=internal`。
- MCP discovered tools 标记为 `visibility=user`。
- AgentService 只根据 metadata 过滤事件，不再维护内部 Tool 名称黑名单。
- `/query` 只做 AgentEvent -> legacy SSE 协议转换，并优先显示 metadata.display_name。

## P8 可靠性

- MCP Tool 已有 timeout。
- 可重试 Tool 仍由 `retryable_tools` 显式控制，避免所有业务写操作被盲目重试。
- 重试实现抽到 `agent/retry.py`，统一次数和递增退避。
- Agent Tool 异常仍会进入 ToolMessage，交回 LLM，由 Workflow/模型决定下一步，而不是把异常伪装成成功。
- AgentLimits 保留最大 step 限制，避免异常循环。

## P9 Evaluation

新增离线评估器：

- 病例信息收集后必须查询患者；
- 患者查询后才允许创建病例；
- need_design=1 的订单流程不能进入处方收集；
- 订单完成后影像仍可通过 image_process 更新；
- 缺少必需 Tool、调用禁止 Tool 都会失败。

## Review 结论

代码层面确认：

1. P7 没有把 Tool 名称判断重新塞回 API。
2. P8 没有默认对所有 Tool 自动重试。
3. P9 不依赖真实 LLM，因此不会把模型措辞变化误判为失败。
4. 现有 `/query` SSE envelope、CORS、AuthContext 注入边界没有改变。
5. 当前仓库没有 CI workflow，因此本轮无法通过 GitHub Actions 远程执行 pytest；已增加本地可执行的 `tests/test_p7_p8_p9.py` 和 `python -m evals.runner`，需要在用户当前虚拟环境中做最终运行验证。
