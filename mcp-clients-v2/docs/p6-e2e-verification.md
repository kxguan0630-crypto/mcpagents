# P6 Agent 全链路验收

> P6 的目标不是继续堆 Agent 框架，而是证明当前 Agent 的 Workflow、State、MCP Tool、认证和 Session 隔离能够稳定工作。

## 一、自动化验收范围

| 类别 | 验收点 | 自动化 |
|---|---|---|
| Case | 患者信息 + 主诉收集后才查询患者 | 是 |
| Case | 查询完成后等待用户明确选择 | 是 |
| Order | 诊断必须询问，可选择不提供 | 是 |
| Order | 影像必须询问，可选择不提供 | 是 |
| Order | 模型必须询问，可选择不提供 | 是 |
| Order | `need_design=1` 完全跳过处方 | 是 |
| Order | `need_design=0` 进入处方询问 | 是 |
| Image | 影像更新前必须完成 `image_process` | 是 |
| Auth | Token 不进入 Graph config | 是 |
| Auth | authorization 不暴露给 LLM Tool Schema | 是 |
| Auth | Tool 执行强制使用 Runtime AuthContext Token | 是 |

对应测试：

```bash
pytest -q tests/test_p6_workflow_matrix.py tests/test_p6_auth_boundary.py
```

## 二、真实环境联调

自动化测试不调用真实 CSN、MCP Server 或业务 HTTP API。以下场景需要在本地部署环境执行：

### 1. 启动 Agent Client

```bash
python3.11 main.py --port 5000
```

### 2. HTTP 健康检查

```bash
curl http://localhost:5000/
```

### 3. 带 Token 调用 `/query`

```bash
curl -X POST http://localhost:5000/query \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <REAL_TOKEN>' \
  -d '{"query":"查询病例","session_id":"p6-case-001"}'
```

### 4. 病例真实链路

验证：

1. 用户提出创建病例。
2. Agent 收集患者基本信息和主诉。
3. 信息完整后，真实调用患者查询 Tool。
4. Tool 返回患者存在/不存在结果。
5. Agent 不自行猜测结果。
6. 患者存在时等待用户明确选择“新建”或“使用已有”。
7. 后续才进入病例创建。

### 5. 订单真实链路

分别验证：

- `need_design=1`：诊断/影像/模型完成询问后不进入处方。
- `need_design=0`：完成诊断/影像/模型询问后进入处方。
- 诊断和影像均允许用户明确选择“不提供”。

### 6. 图片链路

验证前端附件进入 `/query` 后：

```text
HTTP attachments
  -> AgentState attachments
  -> image_process
  -> 影像处理结果
```

并单独验证订单/病例创建完成后的影像更新流程。

### 7. 认证链路

验证：

- 缺失 Authorization -> 401。
- 无效 Token -> 401。
- 有效 Token -> Agent 正常执行。
- LLM Tool Schema 不包含 authorization。
- MCP Server 最终收到的是经过 CSN 验证的真实 Token，而不是模型生成的 Token。

## 三、P6 通过标准

必须同时满足：

- 自动化测试全部通过。
- 病例真实链路通过。
- 订单两条 `need_design` 分支通过。
- 图片处理和订单后影像更新通过。
- JWT/CSN 认证通过。
- 至少两个不同 `session_id` 连续运行时状态互不污染。
- 失败 Tool 不得被 Agent 当成成功业务事实。

只有以上条件全部满足，P6 才标记为“已验收”。
