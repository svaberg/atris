"""Report the Python tools and C++ executable versions."""

from datetime import datetime, timezone
from importlib.metadata import version
import re
import subprocess
import sys

GIT_DESCRIBE_VERSION = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)-(\d+)-g([0-9a-f]+)(-dirty)?$"
)
PEP440_COMMIT = re.compile(r"(\+g[0-9a-f]{7})[0-9a-f]+")


def git_describe_to_pep440(git_version):
    """Convert a git-describe version to its setuptools-scm equivalent."""
    match = GIT_DESCRIBE_VERSION.fullmatch(git_version)
    if match is None:
        return git_version.lstrip("v")

    major, minor, patch, distance, commit, dirty = match.groups()
    pep440_version = (
        major
        + "."
        + minor
        + "."
        + str(int(patch) + 1)
        + ".dev"
        + distance
        + "+g"
        + commit
    )
    if dirty:
        pep440_version += ".d" + datetime.now(timezone.utc).strftime("%Y%m%d")
    return pep440_version


def shorten_pep440_commit(pep440_version):
    """Shorten the commit component of a displayed PEP 440 version."""
    return PEP440_COMMIT.sub(r"\1", pep440_version)


def versions_match(tools_version, executable_version):
    """Return whether package and executable versions identify the same source."""
    executable_version = executable_version.lstrip("v")
    if "-g" not in executable_version:
        return tools_version == executable_version

    executable_commit = executable_version.rsplit("-g", 1)[1].split("-", 1)[0]
    if "+g" not in tools_version:
        return False
    tools_commit = tools_version.split("+g", 1)[1].split(".", 1)[0]
    return tools_commit.startswith(executable_commit)


def report_versions():
    """Print the atris-tools and AtRIS executable versions."""
    tools_version = version("atris-tools")
    displayed_tools_version = shorten_pep440_commit(tools_version)

    try:
        result = subprocess.run(
            ["AtRIS", "--version"],
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError:
        result = None

    output = result.stdout.strip() if result is not None else ""
    if result is None or result.returncode != 0 or not output.startswith("AtRIS "):
        print("AtRIS executable version (PEP 440): unavailable")
        print("atris-tools version (PEP 440):      " + displayed_tools_version)
        print(
            "Warning: could not determine the AtRIS executable version.",
            file=sys.stderr,
        )
        return

    executable_version = output[len("AtRIS ") :]
    displayed_executable_version = git_describe_to_pep440(executable_version)
    print("AtRIS executable version (PEP 440): " + displayed_executable_version)
    print("atris-tools version (PEP 440):      " + displayed_tools_version)
    if not versions_match(tools_version, executable_version):
        print(
            "Warning: the AtRIS executable was built from a different source "
            "revision (atris-tools "
            + displayed_tools_version
            + "; AtRIS "
            + displayed_executable_version
            + ").",
            file=sys.stderr,
        )
