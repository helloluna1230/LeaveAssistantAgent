# 已知限制

这是一个演示参考项目，不是生产系统。

## 数据与范围
- **所有 HR 数据均为模拟数据**（`mcp-server/leave_mcp/mock_data.py`）。没有接入真实
  HR、没有审批、也不会修改任何记录。写操作只会生成不具约束力的预览。

## 身份
- Demo 使用共享的 MCP API key 加明文模拟员工号，而不是真实用户登录。MCP 会先校验
  key，再接受 `x-user-token`，然后执行服务端授权。真实用户认证、令牌刷新以及
  租户/声明校验均未实现。
- `POST /demo/token` 作为前端兼容端点保留，但它返回的是经校验的模拟员工号，而不是
  访问令牌。生产环境请用真实的 Entra ID / IdP 登录替换（见 `docs/security-design.md`）。

## Hosted 模式下的按请求身份
- 本地主机**已实现**：`main.py` 增加了一个纯 ASGI 的 `_IdentityMiddleware`，把每个
  请求的 `x-user-token` / `Authorization` 映射到身份 contextvar（缺失时回退到
  `DEMO_DEFAULT_USER`），因此在 UI 里切换用户会真正切换已验证身份
  （E1001→9 天，E1002→1 天）。对于已部署的 Foundry 运行时，需验证同样的中间件钩子
  是否被采纳；工具调用仍然依赖 toolbox/remote 的 `x-user-token` 转发。

## 依赖平台的 Foundry 原生特性
- **Foundry Toolbox**（`MCP_MODE=toolbox`，默认）：Toolbox 由
  `scripts/create_toolbox.py` 构建，需要**预览版**的 `azure-ai-projects` 以及
  `az login`。用于按用户授权的 `x-user-token` 转发依赖 Toolbox/MCP 连接把自定义请求头
  透传到 Container App MCP；如果你的 Toolbox 配置会剥离这些头，请改用
  `MCP_MODE=remote` 以获得严格的按用户授权，或接入基于 OAuth 的 MCP 连接以代理终端
  用户身份。Toolbox 的 Container App 凭据保存在 Foundry 连接中（`MCP_CONNECTION_ID`）。
- **Foundry IQ** 知识库需在门户中手动创建；在 toolbox 模式下它作为 Toolbox 工具附加
  （在 `create_toolbox.py` 中尽力而为），否则通过 `remote_tools.build_knowledge_tool`
  接入。本地还有一个有据可依的回退方案（`knowledge_local.search` → `search_leave_policy`
  工具），可在离线的 Demo/评估中给出带引用的政策答案；它是基于关键词的，不像 IQ 那样
  语义化。
- **Foundry Memory**：Demo 使用一个基于文件的偏好存储，接口（get/set/delete）保持一致；
  生产环境可替换为 Foundry Memory Store。
- **平台托管的会话**：当 `RESPONSES_STORE=true`（默认）时，Foundry Responses 存储会
  持久化每一轮，并在服务端解析 `previous_response_id`（检索范围限定为已验证的调用方
  身份）——客户端无需重发历史轮次。Hosted 部署会用到持久化的平台存储
  （`FoundryStorageProvider`）；本地运行则自动回退到进程内存储（在运行的主机内多轮可用，
  但重启后丢失）。该会话存储与偏好 Memory 不同：它保存的是问答线程，绝不保存白名单偏好。
  Web UI 会保留一份本地对话缓存以便即时重绘，但回访用户（即使换了新设备）会从平台重建
  线程：主机暴露一个按身份隔离的书签（`GET/POST /session/state`，由 `session_store.py`
  支撑），只保存最后一个 Responses 指针，UI 再通过
  `GET /responses/{id}/input_items` + `GET /responses/{id}` 重建对话。生产环境请把基于
  文件的指针存储换成持久化数据库（如 Cosmos DB）；get/set 接口完全一致。本地的进程内
  Responses 存储会在主机重启时清空，因此保存的指针在重启后可能返回 404——此时 UI 会
  回退到本地缓存。
- **Code Interpreter**：Hosted 模式通过 Foundry Code Interpreter 渲染图表。离线时，
  `analyze_leave_usage`（`analysis.analyze`）会返回可用于绘图的序列（月度用量、已用 vs
  剩余、类型分布、即将过期），但不会绘制图像。**Toolbox/Tool Search** 通过 Foundry 运行时
  演练。Toolbox 构建（`scripts/create_toolbox.py`）使用已确认的 SDK 类
  `CodeInterpreterToolboxTool` 和 `AzureAISearchTool`。⚠️ 通过 Toolbox 使用的 Code
  Interpreter **在一个项目内共享同一个容器——并非按用户隔离**；因此 Agent 只分析调用方
  已经检索到的数据，绝不上传其他用户的数据。若需严格隔离，请使用按 Agent 独立的 Code
  Interpreter 或本地的 `analyze_leave_usage` 路径。
- **Harness**：步数/工具调用预算以及瞬时错误重试在工具层强制执行
  （`agents/harness/runtime.py`，每次运行在 `memory.before_run` 中重置）。模型循环的
  步数统计仍取决于框架是否暴露每步钩子。
- **可观测性**：工具/Skill/Memory/知识/Code Interpreter 的 span 会带脱敏属性发出；
  `trace_id`/`agent_version` 能否呈现到前端响应仍取决于托管层。

## 评估
- `evaluation/run_eval.py` 只确定性地校验后端的安全/异常边界。基于模型的质量指标
  （有据性、工具选择、任务完成度）需要 `azd ai agent eval run --config
  evaluation/hosted_functional_eval.yaml`，针对已部署的 Agent 版本运行。

## 前端
- 极简聊天 UI；本环境未运行 `npm install`。SSE 解析假设事件形态为
  `data: {delta|output_text|...}`；请根据你的主机实际流格式做调整。

## 云端预配
- 本仓库复用已有的 Foundry 项目、模型部署、ACR 和 Container Apps 环境；不包含用于
  `azd provision` 的 `infra/main.bicep` 或 Terraform 模板。
- `azd deploy` 需要 `az login` / `azd auth login`，这属于操作者的职责（不自动执行）。
