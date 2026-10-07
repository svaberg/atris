import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_cpp_sources_follow_clang_format():
    sources = sorted((PROJECT_ROOT / "include").glob("*.hh"))
    sources += sorted((PROJECT_ROOT / "src").glob("*.cc"))
    subprocess.run(
        ["clang-format", "--dry-run", "--Werror", *sources],
        cwd=PROJECT_ROOT,
        check=True,
    )
