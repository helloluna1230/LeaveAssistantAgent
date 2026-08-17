import subprocess
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[3]
UPLOAD_SCRIPT = ROOT / "scripts" / "upload-leave-planning-skill.sh"
SKILL_FILE = ROOT / "skills" / "leave_planning" / "SKILL.md"


def test_build_only_packages_skill_contract_and_planner(tmp_path):
    archive = tmp_path / "leave-planning.zip"

    result = subprocess.run(
        ["bash", str(UPLOAD_SCRIPT), "--build-only", str(archive)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    with ZipFile(archive) as package:
        assert sorted(package.namelist()) == ["SKILL.md", "planner.py"]


def test_skill_requires_registered_planner_tool():
    instructions = SKILL_FILE.read_text(encoding="utf-8")

    assert "MUST call the registered `plan_leave` function tool" in instructions
    assert "Do not reimplement or recalculate the planner logic" in instructions