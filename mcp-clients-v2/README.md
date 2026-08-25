# MCP Agents Client v2

> 基于 **LangGraph + MCP + LLM Tool Calling** 的企业级 Agent Client。
>
> 目标不是把代码写得“高级”，而是让你能顺着源码读懂一次 Agent 请求到底发生了什么。

## 1. 项目简介

`mcp-clients-v2` 负责接收用户请求、维护会话状态、调用 LLM、编排 Workflow、执行 MCP Tools，并通过 SSE 向前端输出统一运行事件。

`mcp-servers` 负责封装真实业务 API；Client 不复制业务 API，而是通过 MCP 调用服务端能力。

当前版本已经从早期的“LLM + Tool Calling 循环”升级为具备 **Workflow Guard、Tool Runtime、认证、审批、失败恢复和 Agent Evaluation** 的 Agent Runtime。

## 2. 整体架构

```text
前端 /query
   │ text + image_list + Authorization
   ▼
Auth Layer
   │
   ▼
AuthContext
   │
   ▼
AgentService
   │
   ▼
LangGraph Agent Runtime
   ├── LLM：理解自然语言、选择工具
   ├── Workflow Registry：确定业务前置条件
   ├── State / Checkpoint：保存多轮执行状态
   └── Tool Runtime
          ├── Metadata
          ├── Approval
          ├── Timeout / Retry
          └── Error Recovery
                  │
                  ▼
             MCP Client
             STDIO Transport
                  │
                  ▼
             mcp-servers
                  │
                  ▼
              Business APIs

        Evaluation / Tests
                 ▲
                 │
          行为契约验证
```

### 核心职责边界

- **LLM**：理解、提取信息、选择允许的 Tool、根据 Tool Result 继续推理。
- **Workflow Runtime**：保证确定性的业务前置条件和流程顺序。
- **Tool Runtime**：统一治理 Tool Metadata、审批、超时、重试和异常。
- **MCP Server**：提供真实业务能力并负责业务 API 调用。
- **Auth**：负责 Token 验证和 Runtime 注入，不让模型管理 Token。
- **AgentService**：把内部 Agent Event 转换成稳定的前端 SSE 协议。

## 3. 目录结构

```text
mcp-clients-v2/
├── agent/
│   ├── graph.py                 # LangGraph Agent Runtime
│   ├── service.py               # Agent Service / SSE 事件转换
│   ├── state.py                 # AgentState
│   ├── events.py                # Agent Event 模型
│   ├── approval_runtime.py      # Tool Approval
│   ├── limits.py                # Agent 执行限制
│   ├── retry.py                 # Tool Retry / Recovery
│   └── workflows/
│       ├── registry.py          # Workflow Registry
│       ├── implementations.py   # 内置业务 Workflow
│       ├── facts.py             # Workflow Facts
│       ├── fact_handlers.py     # 内部状态 / Facts 更新
│       └── tool_adapters.py     # Tool 参数适配
│
├── auth/
│   ├── context.py               # AuthContext
│   └── verifier.py              # JWT / Authorization 验证
│
├── mcp_intergration/
│   └── client.py                # MCP Client / STDIO 通信
│
├── api/
│   ├── app.py                   # FastAPI 应用
│   ├── routes.py                # /query 等 API
│   └── schemas.py               # 请求 / 响应模型
│
├── config/
│   └── servers_config.json      # MCP Server 启动配置
│
├── evals/
│   ├── cases.py                 # Agent Evaluation Cases
│   ├── runner.py                # Evaluation Runner
│   └── README.md                # Evaluation 说明
│
├── tests/                       # 单元 / Runtime / Workflow 测试
├── config.py                    # LLM / MCP / Auth / Checkpoint 配置
├── main.py                      # CLI / HTTP 启动入口
└── README.md
```

## 4. Agent Runtime

核心执行链路：

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
       └─ Timeout
           ↓
        MCP Tool
           ↓
       Tool Result
           ↓
           LLM
           ↓
      Final Answer
```

LangGraph 负责状态化循环，但具体业务流程不通过在 `graph.py` 中不断增加 `if intent == ...` 实现。

Workflow 通过 Registry 提供确定性的前置条件和 Required Action，Runtime 负责执行。例如病例创建中，患者信息和主诉收集完成后必须真正查询患者，不能只由 LLM 回复“系统正在查询”。

## 5. Workflow 与 LLM 的职责边界

### LLM 负责

- 理解自然语言
- 识别用户意图
- 从用户输入中提取业务信息
- 选择允许的 Tool
- 根据 Tool Result 继续对话
- 生成最终自然语言回答

### Workflow Runtime 负责

- 必须收集哪些前置事实
- 哪些 Tool 在当前阶段允许执行
- 哪些动作必须执行
- 用户决策前不得继续后续流程
- `need_design=1` 时完全跳过处方流程
- 订单创建后仍允许通过影像 Tool 更新影像

关键业务规则不全部依赖 Prompt。

## 6. Tool Runtime

Tool 不再只是 LLM 可以调用的函数，而具有运行时元数据，用于区分：

```text
Internal Workflow Tool
        vs
Business MCP Tool
```

内部状态 Tool，例如：

```text
record_workflow_intent
record_case_information
record_patient_decision
record_order_decisions
record_design_decision
```

这些 Tool 可以参与 Agent 内部消息闭环，但不会作为业务 Tool 进度直接展示给用户。

真实 MCP Business Tool，例如：

```text
get_patients_by_name_and_phone
case_add
get_product_list
image_process
```

可以产生用户可见的 Tool Runtime Event：

```text
【处理中】查询患者信息…
【完成】查询患者信息
```

而不是暴露内部状态 Tool。

## 7. MCP

Client 使用 MCP STDIO Transport 与 `mcp-servers` 通信：

```text
mcp-clients-v2
      │ STDIO
      ▼
mcp-servers
      │
      ▼
Business API
```

MCP Server 负责：

- Tool 定义
- Tool 参数 Schema
- 参数校验
- Authorization 接收与校验
- 业务 API 调用
- 业务结果返回

Client 负责 Agent 编排，不把真实业务 API 逻辑复制到 Agent 中。

## 8. Authentication

认证仍沿用原客户端的业务方式，而不是让 Agent 自行解析 Token：

```text
Authorization Header
       ↓
AuthVerifier
       ↓
CSN validate-doctor-token
       ↓
AuthContext
       ↓
AgentService / LangGraph
       ↓
MCP Tool Runtime 自动注入 authorization
       ↓
mcp-server → Business API
```

关键原则：

1. `/query`、`/chat`、`/chat/stream` 进入 Agent 前完成认证。
2. JWT / Token 不写入 `AgentState`、`business_facts` 或 LLM 消息。
3. MCP Server 现有 Tool 可以继续接收 `authorization`，保持业务 Service 兼容。
4. `authorization` 从 LLM 可见的 Tool Schema 中移除。
5. Tool 执行时强制使用已验证的 Runtime Token。
6. CLI 与 HTTP 共用同一套 AuthVerifier。

配置：

```bash
export CSN_URL="你的 CSN 服务地址"
```

HTTP 示例：

```bash
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"session_id":"demo-001","query":"创建病例"}'
```

## 9. Streaming

`/query` 保持 SSE 流式协议。

内部 Runtime 产生统一事件，例如：

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

Service 层负责把 Runtime Event 转换成当前前端使用的 SSE 格式。

因此内部 LangGraph / Workflow / MCP Runtime 可以持续演进，而前端不需要感知内部实现。

## 10. Multimodal / Image Input

前端原来的图片入口继续支持：

```text
/query
  └── image_list
        ↓
AgentState.attachments
        ↓
image_process
        ↓
影像识别结果
```

图片以引用形式进入 Agent，不把大型二进制对象直接塞进 Agent State。

订单创建过程中可以提供影像；订单创建完成后也可以独立执行影像补充 / 更新。影像相关更新不强制绑定在订单创建阶段。

## 11. Reliability / Failure Recovery

Tool 调用失败不会直接假设业务成功。

当前 Runtime 具备：

- Tool Timeout
- 有边界的 Retry
- Retry Backoff
- Agent 最大执行步数
- Tool Error → ToolMessage → LLM Recovery
- Approval Gate

Retry 不是所有 Tool 无条件开启，只有明确允许 Retry 的 Tool 才会进行有限次数重试。

```text
Tool Call
   ↓
Tool Error
   ↓
是否允许 Retry？
   │
  Yes
   ↓
有限次数 Retry + Backoff
   │
   ├── 成功 → Tool Result
   │
   └── 失败 → Tool Error → LLM 决定下一步
```

这样可以避免对具有副作用的写操作进行无限或无条件重复提交。

## 12. Agent Evaluation

项目增加 `evals/`，用于验证 Agent 的**行为契约**，而不仅仅是最终文本。

重点验证：

- 是否调用正确 Tool
- Workflow 顺序是否正确
- 必须调用的 Tool 是否被跳过
- 被禁止的 Tool 是否被调用
- `need_design=1` 是否跳过处方流程
- Tool 失败后是否能够恢复
- 最终业务状态是否符合预期

运行：

```bash
cd mcp-clients-v2
python -m evals.runner
```

核心思想：

> Agent 的正确性不能只看“回答得像不像”，还要验证它是否执行了正确的动作。

## 13. 病例创建流程

```text
患者基本信息 + 主诉
        ↓
查询患者
        ↓
找到？
 ┌────┴────┐
 是        否
 ↓         ↓
用户选择   明确选择新建
 ↓         ↓
使用已有   新建患者
 └────┬────┘
      ↓
   创建病例
```

患者查询是确定性的前置动作，查询结果必须来自真实 MCP Tool。

## 14. 订单创建流程

```text
选择产品
   ↓
确认 need_design
   │
   ├── need_design=1 → 完全跳过处方
   │
   └── need_design=0 → 进入处方流程
                         ↓
                    诊断 / 影像 / 模型
                         ↓
                      创建订单
```

诊断信息和影像信息允许用户暂时不提供，但 Agent 必须明确询问是否需要提供；影像在订单创建后仍可以通过独立 Tool 继续更新。

## 15. 本地运行

### 安装依赖

```bash
cd mcpagents/mcp-clients-v2
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 配置 LLM 和认证

```bash
export BASE_URL="你的 OpenAI-compatible Base URL"
export API_KEY="你的 API Key"
export MODEL_NAME="你的模型名"
export CSN_URL="你的 CSN 服务地址"
```

如需覆盖 MCP 配置：

```bash
export MCP_CONFIG="config/servers_config.json"
```

### 测试

```bash
pytest -q tests
```

### Agent Evaluation

```bash
python -m evals.runner
```

### CLI

CLI 调试必须提供 Token：

```bash
python main.py --token "Bearer YOUR_TOKEN"
```

或者：

```bash
export AGENT_AUTHORIZATION="Bearer YOUR_TOKEN"
python main.py
```

### HTTP API

```bash
python main.py --mode api --host 0.0.0.0 --port 5000
```

健康检查：

```text
http://localhost:5000/
```

业务请求：

```text
POST http://localhost:5000/query
```

HTTP 模式由前端通过 `Authorization: Bearer ...` Header 发送 Token。

## 16. 当前技术能力

当前 Agent Runtime 已具备：

- Python / FastAPI
- LangGraph 状态化 Agent Loop
- LLM Tool Calling
- MCP STDIO / Tool Discovery
- Workflow Registry / Deterministic Guard
- Tool Metadata
- Tool Approval
- Timeout / Retry / Recovery
- Checkpoint / Session State
- JWT / Authorization Context
- SSE Streaming
- Multimodal Image Input
- MCP Business Tool Integration
- Agent Evaluation

## 17. 设计原则

1. **LLM 不负责硬业务规则**：LLM 可以理解用户，但关键前置条件由 Workflow Runtime 保证。
2. **不通过 Tool 名称硬编码业务流程**：Tool Metadata、Workflow Registry 和 Runtime 各司其职。
3. **Agent State 不保存敏感 Token**：Authorization 属于认证上下文，而不是 LLM 可推理的业务数据。
4. **Tool 失败必须真实反馈**：不把异常结果伪装成成功，也不允许无边界重试。
5. **前端协议与 Agent 内部实现解耦**：LangGraph、Workflow、MCP Runtime 可以继续升级，而 `/query` SSE 协议保持稳定。
6. **Agent 正确性需要 Evaluation**：不仅验证最终文本，还验证 Tool 调用和 Workflow 行为。
7. **代码优先可读性**：关键逻辑有中文注释，不为了“高级”引入不必要抽象。

## 18. 当前项目定位

这个项目不是一个简单 Chatbot，也不是单纯 MCP Client。

它更接近一个面向企业业务场景的 **Agent Application Runtime**：

```text
LLM Reasoning
      +
Deterministic Workflow
      +
MCP Tool Runtime
      +
State / Checkpoint
      +
Authentication / Approval
      +
Streaming
      +
Failure Recovery
      +
Evaluation
```

业务能力由 `mcp-servers` 提供，Agent Client 负责把自然语言、业务 Workflow 和工具能力组织成可执行、可恢复、可验证的 Agent。
