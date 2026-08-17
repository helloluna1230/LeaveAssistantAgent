import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for sub in ("", "mcp-server", "skills/leave_planning"):
    p = str(_ROOT / sub) if sub else str(_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

