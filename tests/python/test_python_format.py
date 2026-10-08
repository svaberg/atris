import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_python_sources_follow_black():
    subprocess.run(
        ["black", "--check", "atris_tools", "tests", "docs/conf.py"],
        cwd=PROJECT_ROOT,
        check=True,
    )
