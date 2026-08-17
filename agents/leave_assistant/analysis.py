"""Leave-usage analysis (chart-ready series) from balance + history.

Pure module (no agent_framework) so it is unit-testable. In hosted mode the
Foundry Code Interpreter renders these series as charts; in local mode the agent
returns the structured analysis directly. All inputs are SIMULATED HR data.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date


def _parse(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def analyze(balances: list[dict], history: list[dict]) -> dict:
    monthly: dict[str, float] = defaultdict(float)
    type_distribution: dict[str, float] = defaultdict(float)
    for h in history or []:
        month = _parse(h["start_date"]).strftime("%Y-%m")
        monthly[month] += float(h.get("days", 0))
        type_distribution[h.get("leave_type", "unknown")] += float(h.get("days", 0))

    used_vs_remaining: list[dict] = []
    expiring: list[dict] = []
    for b in balances or []:
        used_vs_remaining.append(
            {
                "leave_type": b["leave_type"],
                "used": b.get("used_days", 0),
                "remaining": b.get("remaining_days", 0),
            }
        )
        if b.get("expiring_days"):
            expiring.append(
                {
                    "leave_type": b["leave_type"],
                    "expiring_days": b["expiring_days"],
                    "expiration_date": b.get("expiration_date"),
                }
            )

    return {
        "summary": {
            "total_used_days": round(sum(type_distribution.values()), 2),
            "leave_types": len(used_vs_remaining),
            "records": len(history or []),
        },
        "charts": {
            "monthly_usage": dict(sorted(monthly.items())),
            "used_vs_remaining": used_vs_remaining,
            "type_distribution": dict(type_distribution),
        },
        "expiring": expiring,
        "note": "Chart-ready series from SIMULATED HR data; the Code Interpreter renders these in hosted mode.",
        "simulated": True,
    }
