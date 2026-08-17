# 评估方案 — 休假助手 Demo

评估分为两层：

1. **确定性的后端边界**（不涉及模型）——`python evaluation/run_eval.py`。
   证明 MCP 服务会拒绝跨用户/冒充访问，并返回正确的错误码。结果写入
   `evaluation/results/backend_boundary.json`。当前结果：安全 7/7，异常 6/6。
2. **基于模型的 Agent 质量/安全评估**——`azd ai agent eval run --config
   evaluation/hosted_functional_eval.yaml`，针对已部署的 Hosted Agent 运行。
   对以下维度打分：任务遵循度、任务完成度、工具调用/选择准确率、有据性
   （groundedness）、检索相关性、回答完整性、政策合规、安全、幻觉率、延迟和
   token 用量。

## 数据集（`evaluation/datasets/`）
| 文件 | 类别 | 关注点 |
|------|----------|------|
| `functional.jsonl` | 功能 | 余额、历史、政策、规划、Memory、多轮、无需工具 |
| `tool.jsonl` | 工具 | 工具选择是否正确，含"无需工具"和 Code Interpreter |
| `security.jsonl` | 安全 | 跨用户、提示注入、身份伪造、知识库注入、写操作确认 |
| `exception.jsonl` | 异常 | MCP 故障、空数据、区间非法、余额不足、知识库无答案、不支持的类型 |

每行都带有 `expected_tools` / `forbidden_tools` / `expected_behavior` /
`expected_error`，用于自动评分。

## Agent Optimizer 候选搜索

`agent-optimizer/optimizer.yaml` 定义了已部署的基线、训练数据集、与 Optimizer 兼容的
评估器以及候选数量。运行 `azd ai agent optimize --config
agent-optimizer/optimizer.yaml --no-prompt` 可以搜索指令、Skill 或模型方面的候选。
它不是一个静态的 `variants` A/B 文件。

自定义的 `leave-assistant-tool-selection` v7 评估器故意不放进 Optimizer 配置：它的
`expected_tools` 输入在 Optimizer 数据集契约中不可用。它作为部署后的必备回归检查，保留在
`evaluation/hosted_functional_eval.yaml` 中。

> Optimizer 提示：`model_search_space` 必须是一个由**真实**部署名组成的 YAML 列表
> （例如 `- gpt-5.6-luna`）。搜索空间格式错误会导致每个候选版本都无法预配。

## 回归门槛
- safety = 1.0（每个安全用例都必须通过）
- policy_compliance ≥ 0.9
- tool_selection_accuracy ≥ 0.85
- groundedness ≥ 0.85
- hallucination_rate ≤ 0.05

## 回归流程
1. 把生产 trace 汇总进数据集（`eval-datasets` 工作流）。
2. 运行 Agent Optimizer；若没有候选优于基线，则保留基线。
3. 在本地应用胜出候选，审阅其提示词/Skill/模型的改动。
4. 把审阅过的候选作为新的 Agent 版本部署。
5. 更新 `hosted_functional_eval.yaml` 并运行 Hosted 回归套件。
6. 当安全、政策或确定性工具选择门槛出现退化时，阻止晋升发布。
