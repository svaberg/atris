from atris_tools.version import (
    git_describe_to_pep440,
    report_versions,
    shorten_pep440_commit,
    versions_match,
)


def test_git_describe_version_is_converted_to_pep440():
    assert git_describe_to_pep440("v3.1.0-5-gabcdef0123") == ("3.1.1.dev5+gabcdef0123")
    assert git_describe_to_pep440("v3.1.0") == "3.1.0"


def test_displayed_commit_is_shortened_without_changing_comparison():
    version = "3.1.1.dev5+gabcdef0123"
    assert shorten_pep440_commit(version) == "3.1.1.dev5+gabcdef0"
    assert versions_match(version, "v3.1.0-5-gabcdef0")
    assert not versions_match(version, "v3.1.0-5-g1234567")


def test_executable_version_error_is_passed_through(tmp_path, monkeypatch, capfd):
    executable = tmp_path / "AtRIS"
    executable.write_text("#!/bin/sh\necho 'missing runtime library' >&2\nexit 1\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(
        "atris_tools.version.version",
        lambda distribution: "3.2.0",
    )

    report_versions()

    output = capfd.readouterr()
    assert "missing runtime library" in output.err
    assert "could not determine the AtRIS executable version" in output.err
