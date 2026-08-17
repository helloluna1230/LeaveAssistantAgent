# Agent Optimizer

This folder contains the Microsoft Foundry Agent Optimizer experiment spec for
Leave Assistant. Run all commands from the repository root.

## Files

- `optimizer.yaml`: deployed baseline, dataset, compatible evaluators, and candidate settings.
- `../.agent_configs/baseline/`: baseline prompt and skill snapshot consumed by the SDK.

`.agent_configs/` remains at the repository root because `azd ai agent optimize apply`
always writes downloaded candidates there and the Agent Optimizer SDK uses that location
by default.

## Run

1. Sign in and verify the target Agent:

   ```bash
   az login
   azd auth login
   azd ai agent show leave-assistant
   ```

2. Confirm that `agent.version` in `optimizer.yaml` is active and that the configured
   baseline, evaluation, and optimization model deployment names exist in the project.

3. When the production prompt or planning skill changes, refresh the baseline snapshot:

   ```bash
   cp agents/instructions/leave_assistant.md .agent_configs/baseline/instructions.md
   cp skills/leave_planning/SKILL.md \
     .agent_configs/baseline/skills/leave-planning/SKILL.md
   ```

4. Start optimization and wait for candidate scores:

   ```bash
   azd ai agent optimize \
     --config agent-optimizer/optimizer.yaml \
     --no-prompt
   ```

5. Inspect a completed or asynchronous run:

   ```bash
   azd ai agent optimize status <optimization-job-id>
   ```

6. If a candidate clearly beats the baseline, apply it locally and review the generated
   `.agent_configs/` changes:

   ```bash
   azd ai agent optimize apply --candidate <candidate-id>
   ```

   Do not use `optimize deploy` directly. If the baseline wins, apply nothing. After local
   review, deploy the selected candidate as a new Agent version, update
   `evaluation/hosted_functional_eval.yaml`, and run the hosted regression suite.

## Evaluator boundary

Do not add `leave-assistant-tool-selection` v7 to `optimizer.yaml`. Optimizer exposes
`query`, `response`, `tool_calls`, and `tool_definitions`, but not the dataset's
`expected_tools` field required by v7. Deterministic tool-selection validation remains in
`evaluation/hosted_functional_eval.yaml` for post-deployment regression.

Latest verified run on 2026-08-17: job
`opt_01c4911c8cfc4d9fb04908c5640e20df`; baseline `0.706`, system-prompt candidate
`0.688`, skill candidate `0.629`. The baseline won, so no candidate was applied or deployed.