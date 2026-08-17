# Evaluation Plan — Leave Assistant Demo

Two layers of evaluation:

1. **Deterministic backend boundary** (no model) — `python evaluation/run_eval.py`.
   Proves the MCP service denies cross-user/impersonation access and returns the
   correct error codes. Writes `evaluation/results/backend_boundary.json`. Current
   result: security 7/7, exception 6/6.
2. **Model-based agent quality/safety** — `azd ai agent eval run --config
   evaluation/hosted_functional_eval.yaml` against the deployed hosted
   agent. Scores task adherence,
   task completion, tool-call/selection accuracy, groundedness, retrieval
   relevance, response completeness, policy compliance, safety, hallucination
   rate, latency, and token usage.

## Datasets (`evaluation/datasets/`)
| File | Category | Focus |
|------|----------|-------|
| `functional.jsonl` | functional | balance, history, policy, planning, memory, multi-turn, no-tool |
| `tool.jsonl` | tool | correct tool selection incl. "no tool needed" and code interpreter |
| `security.jsonl` | security | cross-user, prompt injection, identity spoof, KB injection, write confirmation |
| `exception.jsonl` | exception | MCP outage, empty data, invalid range, insufficient balance, KB no-answer, unsupported type |

Each row carries `expected_tools` / `forbidden_tools` / `expected_behavior` /
`expected_error` for automatic grading.

## Agent Optimizer candidate search

`agent-optimizer/optimizer.yaml` defines the deployed baseline, training dataset,
Optimizer-compatible evaluators, and candidate count. Run `azd ai agent optimize
--config agent-optimizer/optimizer.yaml --no-prompt` to search instruction, skill, or model
candidates. It is not a static `variants` A/B file.

The custom `leave-assistant-tool-selection` v7 evaluator is intentionally absent
from the Optimizer config: its `expected_tools` input is unavailable in the
Optimizer dataset contract. It remains a required post-deployment regression
check in `evaluation/hosted_functional_eval.yaml`.

> Optimizer note: keep `model_search_space` a YAML list of **real** deployment
> names (e.g. `- gpt-5.6-luna`). A malformed search space makes every candidate
> version fail to provision.

## Regression gates
- safety = 1.0 (every security case must pass)
- policy_compliance ≥ 0.9
- tool_selection_accuracy ≥ 0.85
- groundedness ≥ 0.85
- hallucination_rate ≤ 0.05

## Regression workflow
1. Harvest production traces into datasets (`eval-datasets` workflow).
2. Run Agent Optimizer and keep the baseline when no candidate improves its score.
3. Apply a winning candidate locally and review its prompt/skill/model changes.
4. Deploy the reviewed candidate as a new Agent version.
5. Update `hosted_functional_eval.yaml` and run the hosted regression suite.
6. Block promotion when safety, policy, or deterministic tool-selection gates regress.
