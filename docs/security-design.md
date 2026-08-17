# 安全设计 — 休假助手 Demo

所有 HR 数据均为**模拟数据**。本文档描述系统的信任边界，以及该 Demo 如何满足安全
验收标准（§23.2）。

## 信任边界与身份

```
用户登录（演示中为单一固定用户 E1001）
  → 前端把模拟员工号发送给 Hosted Agent（/responses）
  → Agent 用模拟目录校验该员工号
  → Agent/Toolbox 使用 MCP_API_KEY 向 HR MCP 认证
  → Agent 通过 x-user-token 转发模拟员工号
  → MCP 只有在校验 API key 通过后才接受该请求头
  → MCP 将员工号映射为 Principal，并对每次调用进行授权（service.py）
```

`MCP_API_KEY` 是 MCP 唯一的认证机制，通过 `X-API-Key` 请求头传递；调用方身份则以
明文模拟员工号的形式放在 `x-user-token` 中。当 API key 缺失或错误时，中间件会直接
丢弃调用方身份。随后 `auth.py` 从模拟目录解析该身份，`service.py` 在服务端对每个操作
进行授权。

### 各模式下的身份转发
- **`toolbox`（默认）。** Agent 连接到一个受治理的 Foundry Toolbox MCP 端点。Toolbox
  使用 `ai.azure.com` bearer（凭据由 Foundry 连接持有，不写在 Agent 代码里）放在
  `Authorization` 头向平台认证。模拟员工号通过 `x-user-token` 转发，而 Foundry MCP
  连接向 Container App 提供 `x-api-key`。
- **`remote`。** Agent 直接调用 Container App 上的 MCP，把已验证的 API key 放在
  `x-api-key`，模拟员工号放在 `x-user-token`。

代码中强制执行的规则：
- **不信任模型/客户端提供的员工号。** `service._resolve_target` 会忽略任何与已验证
  调用方不匹配的 `employee_id`（经理对直属下属余额的有限汇总除外）。测试：
  `mcp-server/tests/test_authz.py`、`tests/security/test_authorization_boundary.py`。
- **不泄露存在性。** 跨用户拒绝统一返回通用的 `FORBIDDEN`，既不指明目标，也不透露
  其是否存在。
- **经理最小权限。** `M1001` 只能看到直属下属的**余额汇总**，看不到他们的历史记录。
- **生产身份必须依赖 IdP。** 模拟员工号并不能证明终端用户身份。生产系统必须校验
  IdP 令牌，并从可信声明中推导员工映射，然后再把身份转发给 MCP。

## 防护措施（对应 §14）
| 威胁 | 缓解措施 | 证据 |
|--------|-----------|------|
| 提示注入（"忽略规则……"） | 系统指令把工具/文档内容视为数据而非命令；MCP 授权独立于模型 | `evaluation/datasets/security.jsonl`（`sec-prompt-injection`） |
| 身份冒充（"我的员工号是 E1002"） | 身份来自请求上下文，而非模型文本或工具参数 | `test_impersonation_via_employee_id_is_denied` |
| 知识库间接注入 | 检索到的文本被当作数据，Agent 绝不执行其中嵌入的指令 | `sec-kb-injection` |
| 敏感数据泄露 | 服务端授权 + 通用拒绝 + 输出最小化 | `test_denial_does_not_leak_target_identity` |
| 未确认的写操作 | 写工具使用 `@tool(approval_mode="always_require")`（人工确认，HITL） | `local_tools.create_leave_request_preview`、`delete_my_preferences` |

## 遥测中的数据处理
- `observability.redact()` 会屏蔽 bearer 令牌，并对员工号做部分脱敏。
- Span 只记录脱敏后的用户号、工具名、状态、错误类型、延迟——绝不记录完整令牌、
  密钥或未脱敏的业务数据。
- 偏好 Memory 只持久化白名单字段（`preference_store.ALLOWED_KEYS`）；余额/历史绝不存储。

## `/demo/token` 兼容端点
Web Demo 保留了这个路由名以保持兼容，但它只返回经目录校验的模拟员工号，并不签发访问
令牌。演示前端使用单一固定演示用户（E1001），不提供用户切换。在生产环境中，请用真实的
Entra ID / IdP 登录替换该路由与固定演示身份。
