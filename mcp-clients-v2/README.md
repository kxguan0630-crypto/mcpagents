# MCP Agents Client v2

> 基于 **LangGraph + MCP + LLM Tool Calling** 的企业级 Agent Client。

当前版本在 P7-P9 基础上继续完善 **P10 可观测性、P11 行为评估、P12 Human-in-the-loop、P13 Memory 分层、P14 MCP Transport 边界**。

## P10-P14 能力总览

```text
LLM Reasoning
      +
Deterministic Workflow
      +
Tool Runtime
      +
Authentication
      +
Approval / Human-in-the-loop
      +
Checkpoint / Session Memory
      +
Long-term Memory Interface
      +
Structured Run Trace
      +
Behavior Evaluation
      +
MCP Transport Boundary
      +
SSE Streaming
```

## 1. 核心架构

```text
                    Frontend /query
                          │
                    AuthContext
                          │
                    AgentService
                          │
              ┌───────────▼───────────┐
              │    LangGraph Runtime  │
              │                       │
              │ LLM → Workflow Guard  │
              │       → Tool Runtime  │
              │       → MCP Tool      │
              │       → LLM           │
              └───────────┬───────────┘
                          │
                    MCP Transport
                          │
                    mcp-servers
                          │
                    Business APIs

        ┌─────────────────┴─────────────────┐
        │                                   │
 Observability / Trace              Evaluation
        │                                   │
 run → node → tool                  tool/order/facts

        Memory layers:
        Session / Checkpoint → Business Memory
```

核心职责边界：

- **LLM**：理解自然语言、提取信息、选择 Tool、生成回答。
- **Workflow Runtime**：保证确定性的业务前置条件和流程顺序。
- **Tool Runtime**：治理 Metadata、Approval、Timeout、Retry、Error Recovery。
- **MCP Server**：提供真实业务能力并负责 API 调用和服务端参数校验。
- **Auth**：验证 Token 并通过 Runtime Context 注入 MCP Tool。
- **Observability**：记录一次 Run 的阶段、Tool、状态和错误。
- **Evaluation**：验证 Agent 行为契约，而不只检查最终文本。

## 2. Agent Runtime

```text
User Request
    ↓
   LLM
    │
    ├── 普通回答 → Final Answer
    │
    └── Tool Call
           ↓
     Workflow Guard
           ↓
      Tool Runtime
       ├─ Approval
       ├─ Retry
       ├─ Timeout
       └─ Error Recovery
           ↓
        MCP Tool
           ↓
       Tool Result
           ↓
           LLM
           ↓
      Final Answer
```

LangGraph 负责状态化循环，但业务 Workflow 不通过在 `graph.py` 中不断增加 `if intent == ...` 实现。

Workflow Registry 提供确定性的 Required Action。例如患者信息和主诉齐全后，Runtime 必须真实查询患者，而不能只让 LLM 回复“正在查询”。fileciteturn349file0L2-L2

## 3. LLM 与 Workflow 边界

### LLM 负责

- 理解用户自然语言
- 提取业务信息
- 识别业务意图
- 选择允许的 Tool
- 根据 Tool Result 继续推理
- 生成自然语言回答

### Workflow Runtime 负责

- 前置条件
- Tool 顺序
- Required Action
- 用户决策等待
- `need_design=1` 完全跳过处方流程
- 订单完成后仍允许影像更新

**原则：关键业务规则不能全部依赖 Prompt。**

## 4. Tool Runtime

Tool 分为两类：

```text
Internal Workflow Tool
        vs
Business MCP Tool
```

内部事实 Tool：

```text
record_workflow_intent
record_case_information
record_patient_decision
record_order_decisions
record_design_decision
```

它们参与 LLM 消息闭环，但不作为用户可见的业务 Tool 进度。

真实 MCP Business Tool 例如：

```text
get_patients_by_name_and_phone
case_add
get_product_list
image_process
```

用户可见事件：

```text
【处理中】查询患者信息…
【完成】查询患者信息
```

## 5. P10：Observability

一次 Agent Run 现在可以形成结构化 Trace：

```text
run_start
   ↓
node_end: llm
   ↓
tool_start: get_patients...
   ↓
tool_end: get_patients... / success
   ↓
node_end: tools
   ↓
answer
   ↓
run_end
```

`AgentRun` 记录：

- `run_id`
- `session_id`
- start/end
- status/error
- duration
- node / tool / approval 等事件
- 可序列化 `snapshot()`

当前实现保持轻量，默认输出日志；后续可以把 Tracker 替换为 OpenTelemetry、LangSmith 或公司内部 Trace Sink，而不修改 Graph。

## 6. P11：Behavior Evaluation

Evaluation 从“最终回答像不像”升级为“Agent 是否做了正确动作”。

`evals/behavior.py` 提供：

```text
required_tools
forbidden_tools
required_order
required_facts
```

示例：

```text
患者信息完整
    ↓
必须查询患者
    ↓
用户决策
    ↓
允许 case_add
```

如果 Agent 直接 `case_add`，行为契约应判定失败。

运行：

```bash
python -m evals.runner
```

## 7. P12：Human-in-the-loop

有副作用的 Tool 可以经过 Approval Policy：

```text
LLM Tool Decision
      ↓
Approval Policy
      ↓
需要确认？
  ┌───┴───┐
 No      Yes
  ↓        ↓
Execute  interrupt
           ↓
       用户确认/拒绝
           ↓
       LangGraph resume
           ↓
         Execute
```

审批 ID 与原始 Tool Call 绑定，保证 LangGraph 从 interrupt 恢复时不会重复创建审批请求。审批决定在 Agent 成功恢复后才消费，resume 失败仍可重试。fileciteturn362file0L2-L2

## 8. P13：Memory 分层

不再把所有状态都叫“Memory”：

```text
短期对话
  └── SessionMemory

可恢复运行状态
  └── LangGraph Checkpoint

长期业务记忆
  └── LongTermMemory
       ├── get
       ├── put
       └── delete
```

长期记忆只允许明确的业务事实进入，不保存 Authorization、Token 或完整消息。

当前提供 `InMemoryLongTermMemory` 作为开发/测试实现，生产环境可实现同一 Protocol 接入 Redis/数据库。

## 9. P14：MCP Transport

当前业务仍使用 **STDIO**，没有为了“支持更多协议”而虚构一个 HTTP MCP Server。

但 Agent 层已经通过 `MCPTransport` 定义连接边界：

```text
Agent Runtime
      ↓
MCPTransport
      ├── STDIO（当前）
      └── Streamable HTTP（后续可插拔）
```

`MCPTransport` 只定义：

- connect
- list_tools
- call_tool
- close

因此未来增加远程 MCP Transport 不需要修改 Workflow / Agent Graph。

## 10. Authentication

```text
Authorization Header
       ↓
AuthVerifier
       ↓
AuthContext
       ↓
AgentService / LangGraph
       ↓
MCP Tool Runtime
       ↓
MCP Server
```

原则：

1. Token 不进入 AgentState。
2. Token 不进入 LLM Message。
3. Tool Schema 中隐藏 `authorization`。
4. MCP Tool 执行时从已验证 Runtime Context 注入 Token。

## 11. Streaming

`/query` 保持原有 SSE 协议。

内部事件包括：

```text
agent_start
workflow_start
tool_start
tool_end
tool_error
approval_required
answer
done
```

Service 层负责把内部 Runtime Event 转成前端协议，因此前端不需要了解 LangGraph、Workflow 或 MCP 的内部结构。

## 12. Multimodal / Image Input

```text
/query
  └── image_list
        ↓
AgentState.attachments
        ↓
image_process
        ↓
影像结果
```

图片只保存引用，不把二进制塞进 checkpoint。

订单创建过程中可以提供影像；订单创建完成后也可以通过独立影像 Tool 更新。

## 13. Reliability

当前 Runtime 具备：

- Tool Timeout
- 有边界 Retry
- Retry Backoff
- Agent 最大执行步数
- Tool Error → ToolMessage → LLM Recovery
- Approval Gate
- Checkpoint / Resume

对于具有副作用的写操作，不进行无条件无限重试。

## 14. 病例创建 Workflow

```text
患者基本信息 + 主诉
        ↓
真实查询患者
        ↓
用户选择
   ┌────┴────┐
新建        已有
 ↓            ↓
case_add    选择 patient
```

查询结果必须来自 MCP Business Tool。

## 15. 订单创建 Workflow

```text
选择产品
   ↓
确认 need_design
   │
   ├── 1 → 完全跳过处方
   │
   └── 0 → 进入处方流程
             ↓
        诊断 / 影像 / 模型
             ↓
          创建订单
```

诊断和影像可以暂不提供，但流程必须明确询问用户是否提供；订单创建后仍允许独立更新影像。

## 16. 目录结构

```text
mcp-clients-v2/
├── agent/
│   ├── graph.py
│   ├── service.py
│   ├── state.py
│   ├── memory.py
│   ├── observability.py
│   ├── mcp_transport.py
│   ├── approval_runtime.py
│   ├── approval_manager.py
│   ├── checkpoint*.py
│   ├── limits.py
│   └── workflows/
├── auth/
├── mcp_intergration/
├── api/
├── evals/
│   ├── cases.py
│   ├── behavior.py
│   └── runner.py
├── tests/
├── config/
└── main.py
```

## 17. 本地运行

```bash
cd mcpagents/mcp-clients-v2
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q tests
python -m evals.runner
```

HTTP：

```bash
python main.py --mode api --host 0.0.0.0 --port 5000
```

请求：

```text
POST http://localhost:5000/query
Authorization: Bearer YOUR_TOKEN
```

## 18. 设计原则

1. **LLM 不负责硬业务规则。**
2. **不通过 Tool 名称硬编码业务流程。**
3. **Authorization 属于 Runtime Context，不属于 LLM State。**
4. **Tool 失败必须真实反馈。**
5. **前端 SSE 协议与 Agent 内部实现解耦。**
6. **Agent 正确性必须能够被行为契约验证。**
7. **Memory 分层，避免把会话、Checkpoint、业务记忆混为一谈。**
8. **Transport 可替换，但当前只承诺已经真实实现的 STDIO。**
9. **保持代码可读，不为了“高级”引入不必要框架。**

## 19. 当前技术定位

项目已经从简单的 `LLM → Tool → LLM` 循环升级为：

> **面向企业业务 Workflow 的 Agent Application Runtime**

核心能力：

- Python / FastAPI
- LangGraph Stateful Agent Loop
- LLM Tool Calling
- MCP Tool Discovery / STDIO
- Deterministic Workflow Guard
- Tool Runtime Metadata
- Approval / Human-in-the-loop
- Timeout / Retry / Recovery
- Checkpoint / Resume
- Session / Long-term Memory Boundary
- Structured Agent Run Trace
- Behavior Evaluation
- JWT / Authorization Context
- SSE Streaming
- Multimodal Image Input
