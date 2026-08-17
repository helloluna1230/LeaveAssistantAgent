import sys
from pathlib import Path

# Make the repo importable the same way the agent package does at runtime.
_ROOT = Path(__file__).resolve().parents[2]
for sub in ("", "mcp-server", "skills/leave_planning"):
    p = str(_ROOT / sub) if sub else str(_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

