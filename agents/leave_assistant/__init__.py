"""Leave Assistant hosted agent package.

Bootstraps import paths so the agent can reuse the mock HR MCP service and the
Leave Planning Skill directly in local mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _sub in ("mcp-server", "skills/leave_planning"):
    _p = str(_REPO_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
