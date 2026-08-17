"""Agent harness configuration: execution limits, retry, and HITL policy.

The Agent Framework provides the loop, tool selection, context management, and
lifecycle hooks. This module centralizes the demo's harness *policy* so it is
explicit and reviewable, and exposes helpers the entrypoint/hooks apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    backoff_seconds: float = 1.0
    # Transient MCP/service errors worth retrying; authz/validation are NOT retried.
    retryable_error_codes: tuple[str, ...] = ("SERVICE_UNAVAILABLE",)


@dataclass(frozen=True)
class HarnessConfig:
    max_steps: int = 12
    max_tool_calls: int = 20
    # Tools that mutate external state require explicit user confirmation (HITL).
    # Enforced at the tool layer via @tool(approval_mode="always_require").
    write_tools: tuple[str, ...] = ("create_leave_request_preview", "delete_my_preferences")
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    # On context overflow, keep these signals when compacting history.
    compaction_keep: tuple[str, ...] = (
        "verified_user_identity",
        "active_leave_constraints",
        "latest_tool_results",
        "cited_policy_sections",
        "pending_confirmation",
    )


DEFAULT = HarnessConfig()


def is_write_tool(name: str, config: HarnessConfig = DEFAULT) -> bool:
    return name in config.write_tools


def should_retry(error_code: str, attempt: int, config: HarnessConfig = DEFAULT) -> bool:
    return attempt < config.retry.max_attempts and error_code in config.retry.retryable_error_codes
