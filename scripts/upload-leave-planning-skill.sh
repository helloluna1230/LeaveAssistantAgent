#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BUILD_ONLY=false
CLEANUP_ARCHIVE=false

if [[ $# -eq 0 ]]; then
  ARCHIVE="$(mktemp --suffix=.zip "${TMPDIR:-/tmp}/leave-planning.XXXXXX")"
  CLEANUP_ARCHIVE=true
elif [[ $# -eq 2 && "$1" == "--build-only" ]]; then
  BUILD_ONLY=true
  ARCHIVE="$2"
else
  echo "Usage: bash scripts/upload-leave-planning-skill.sh [--build-only <output.zip>]" >&2
  exit 2
fi

if [[ "$CLEANUP_ARCHIVE" == "true" ]]; then
  trap 'rm -f "$ARCHIVE"' EXIT
fi

python3 - "$ARCHIVE" <<'PY'
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

archive = Path(sys.argv[1]).resolve()
skill_dir = Path("skills/leave_planning")
members = ("SKILL.md", "planner.py")

archive.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(archive, "w", ZIP_DEFLATED) as package:
    for member in members:
        package.write(skill_dir / member, member)

with ZipFile(archive) as package:
    packaged = tuple(sorted(package.namelist()))
expected = tuple(sorted(members))
if packaged != expected:
    raise SystemExit(f"ERROR: invalid skill package members: {packaged!r}")

print(f"Built {archive}: {', '.join(packaged)}")
PY

if [[ "$BUILD_ONLY" == "true" ]]; then
  exit 0
fi

command -v azd >/dev/null 2>&1 || { echo "ERROR: azd not installed." >&2; exit 1; }

azd ai skill create leave-planning \
  --file "$ARCHIVE" \
  --force \
  --no-prompt