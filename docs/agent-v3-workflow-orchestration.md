# Agent v3 Workflow Orchestration

## 这次改造解决什么

这一版不是把所有业务逻辑都重新写成一个“大状态机”，而是把职责明确拆成四层：

```text
前端 /query
    ↓
Agent Input（文本 + 图片/附件引用）
    ↓
LLM（理解、提取、对话）
    ↓
LangGraph（State / Node / Edge / interrupt / checkpoint）
    ↓
业务 Workflow Rules（确定性前置条件）
    ↓
MCP Tools（真正执行后端业务）
```

## 病例

```text
患者信息 + 主诉
    ↓
get_patients_by_name_and_phone
    ↓
用户决定：新建 / 使用已有
    ↓
case_add
```

不能因为 LLM 推断“患者不存在”就跳过真实查询。

## 订单

```text
病例确认
 ↓
订单存在性检查（新建病例可按业务规则跳过）
 ↓
产品选择
 ↓
need_design
 ↓
诊断：每次询问，可选择不提供
 ↓
影像：每次询问，可选择不提供
 ↓
模型：每次询问
 ↓
need_design=0 → 进入处方
need_design=1 → 完全跳过处方
 ↓
case_order_add
```

## 影像

图片是 Agent 的输入能力，不是 MCP Tool 本身。

```text
前端上传
 ↓
Agent attachments
 ↓
image_process
 ↓
识别结果
 ↓
按业务需要保存/更新
```

影像能力可以在订单创建期间使用，也可以在订单创建完成后独立使用。
因此不能把 `image_process` 设计成 `OrderCreationWorkflow` 的私有工具。

## 阅读代码的入口

建议按下面顺序阅读：

1. `mcp-clients-v2/agent/state.py`：Agent 保存什么状态
2. `mcp-clients-v2/agent/graph.py`：LangGraph 怎么运行
3. `mcp-clients-v2/agent/workflows/rules.py`：哪些业务规则是硬门禁
4. `mcp-clients-v2/agent/workflows/case_creation.py`：病例业务顺序
5. `mcp-clients-v2/agent/workflows/order_creation.py`：订单业务顺序
6. `mcp-clients-v2/agent/workflows/face_consultation.py`：面诊/影像独立能力
7. `mcp-clients-v2/api/schemas.py`：前端输入协议
8. `mcp-clients-v2/api/app.py`：HTTP 到 Agent 的入口

## 本阶段原则

- 不改变 MCP Server 的业务 API 实现。
- 不建立一个复杂的通用 Workflow Engine。
- 不让 LLM 决定确定性的安全前置条件。
- 不让 MCP Tool docstring 继续承担整个业务流程的控制职责。
- 不把图片二进制写进 LangGraph checkpoint。
- 旧 `/query` 与 `query/image_list` 字段在客户端内部保留兼容层；前端协议的最终字段仍以原客户端实际契约为准，下一阶段继续逐项核对。
