# Evaluation

本项目把 evaluation 分成两个互补层次。完整指标和门禁设计见
[`../docs/evaluation-plan.md`](../docs/evaluation-plan.md)。

| 层次 | 运行位置 | 目标 | 是否调用模型 |
|------|----------|------|--------------|
| Backend boundary | 本地 | 验证跨用户访问拒绝、身份边界和稳定错误码 | 否 |
| Hosted agent quality | Microsoft Foundry | 验证真实托管 Agent 的意图理解、任务遵循和工具选择 | 是 |
| Agent Optimizer | Microsoft Foundry | 搜索 instruction、skill 或 model 候选并与 baseline 比较 | 是 |

## 前置条件

在仓库根目录执行：

```bash
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install -r evaluation/requirements.txt

az login
azd auth login
azd extension install azure.ai.agents
```

托管评测还要求目标 Agent 已部署且处于 active 状态。当前可执行配置位于
[`hosted_functional_eval.yaml`](hosted_functional_eval.yaml)，运行前检查：

- `agent.name` 和 `agent.version` 指向要评测的托管版本。
- `dataset.local_uri` 指向仓库内的 `functional.jsonl`。
- 自定义 evaluator 的 `version` 是 Foundry 中已注册的版本。
- `options.eval_model` 是当前 Foundry 项目中存在的模型部署名。

## 1. 执行本地 backend boundary

```bash
.venv/bin/python evaluation/run_eval.py
```

该命令读取 security 和 exception 数据集，结果写入
`evaluation/results/backend_boundary.json`。它不依赖托管 Agent，也不产生模型费用。

## 2. 执行托管 Agent evaluation

```bash
azd ai agent eval run \
   --config evaluation/hosted_functional_eval.yaml \
   --no-prompt
```

命令会调用配置中的真实 hosted agent，并打印 evaluation ID 和 run ID。当前 suite
执行以下 evaluator：

- `builtin.intent_resolution`
- `builtin.task_adherence`
- `leave-assistant-tool-selection`（自定义 deterministic code evaluator）
- `leave-assistant-functional-smoke`（项目 rubric evaluator）

`azd` 会把当前远端 evaluation definition 记录在环境变量 `LAST_EVAL_ID` 中。同一套
配置复测时保留该值，才能把多次 run 放在同一个 group 中比较：

```bash
azd env get-value LAST_EVAL_ID
```

如果修改了 suite 名、数据集或 evaluator version，应在下一次 run 前清空旧 ID，让 CLI
按照更新后的 YAML 创建新的远端 definition；否则它会继续复用旧 evaluator：

```bash
RESET_LAST_EVAL_ID=true bash scripts/azd-env-sync.sh
```

查看最近一次 evaluation：

```bash
azd ai agent eval show
```

使用运行输出中的 ID 导出完整结果：

```bash
EVAL_ID=<evaluation-id>
EVAL_RUN_ID=<evaluation-run-id>

azd ai agent eval show "$EVAL_ID" \
   --eval-run-id "$EVAL_RUN_ID" \
   --out-file evaluation/results/hosted-eval.json
```

通过标准：run 状态为 `completed`、`result_counts.errored` 为 `0`，并逐项检查自定义
工具选择 evaluator 是否通过。不要只看 overall passed；model-based evaluator 和
deterministic evaluator 应分别分析。

## 3. 执行 Agent Optimizer

Optimizer 已独立到 [`../agent-optimizer/`](../agent-optimizer/README.md)。配置入口为
`agent-optimizer/optimizer.yaml`；前置检查、baseline 同步、运行、候选审查与部署后回归
步骤均维护在该目录的 README 中。

## 4. 更新工具选择 evaluator

[`tool_selection_evaluator.py`](tool_selection_evaluator.py) 根据数据集中的
`expected_tools` 与托管轨迹里的实际 `tool_calls` 进行确定性评分。更新代码后：

```bash
# 1) 先验证本地评分契约
.venv/bin/python -m pytest tests/test_tool_selection_evaluator.py -q

# 2) 从当前 azd 环境读取 Foundry 项目端点
export FOUNDRY_PROJECT_ENDPOINT="$(azd env get-value FOUNDRY_PROJECT_ENDPOINT)"

# 3) 注册一个新的 evaluator version；命令会打印 name:version
.venv/bin/python scripts/register_tool_selection_evaluator.py
```

注册成功后，编辑 [`hosted_functional_eval.yaml`](hosted_functional_eval.yaml)：

1. 把 `leave-assistant-tool-selection` 的 `version` 改为刚创建的版本。
2. 同步修改 suite 的 `name` 后缀，避免不同 evaluator 版本的运行混在一起。
3. 如 Agent 已重新部署，同时更新 `agent.version`。
4. 执行 `RESET_LAST_EVAL_ID=true bash scripts/azd-env-sync.sh`，避免复用旧的远端
   evaluation definition。
5. 再执行上一节的 `azd ai agent eval run` 并导出结果。

`azd ai agent eval update --evaluator-only` 面向带 `local_uri` 的 rubric evaluator；本项目的
Python code evaluator 必须使用注册脚本创建 catalog version，不能用该命令替代。

不要为当前 hosted Toolbox target 加回 `builtin.tool_call_accuracy`。该 target 的运行轨迹
包含真实 `tool_calls`，但不包含内置 evaluator 所需的 `tool_definitions`，会导致每条样本
都进入 evaluator error。自定义 evaluator 直接依据 `expected_tools` 评分，覆盖本项目需要的
工具选择信号。

## 文件说明

- `datasets/{functional,tool,security,exception}.jsonl`：评测数据集。
- `run_eval.py`：本地 deterministic backend-boundary runner。
- `tool_selection_evaluator.py`：自定义工具选择 evaluator。
- `hosted_functional_eval.yaml`：当前可直接执行、应纳入版本控制的 hosted suite。
- `results/`：运行生成的结果；该目录内容默认被 Git 忽略。

`tool.jsonl` 中的 Code Interpreter 用例要求 Agent 先通过 MCP 取得用户数据，再在托管
运行时进行分析或绘图。Agent Optimizer 配置和说明见
[`../agent-optimizer/`](../agent-optimizer/README.md)。
