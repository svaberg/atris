import importlib
from types import SimpleNamespace

import pytest


ENTRY_POINT_HELP = (
    (
        "atris-nrlmsis-to-psf",
        "nrlmsis2psf",
        ("does not download atmosphere data", "multiple input tables require --output"),
    ),
    (
        "atris-psf-to-gdml",
        "psf2gdml",
        ("output defaults to the input basename", "does not run atris"),
    ),
    (
        "atris-generate-macros",
        "atrismacrogen",
        ("does not run atris", "refuses to overwrite"),
    ),
    (
        "atris-stage-phantoms",
        "phantoms",
        ("does not create response tables", "dummy table"),
    ),
    (
        "atris-clone",
        "clone_run",
        ("simulation results", "does not run or scatter"),
    ),
    (
        "atris-scatter",
        "scatter",
        ("does not repartition existing work", "does not run or gather"),
    ),
    (
        "atris-run",
        "run_chunks",
        ("do not launch workers", "never interrupts a running chunk"),
    ),
    (
        "atris-gather",
        "gather",
        ("partial files", "does not run missing chunks"),
    ),
    (
        "atris-postprocess",
        "postprocess",
        ("replacing existing processed files", "does not gather chunk histograms"),
    ),
    (
        "atris-plot",
        "plotting",
        ("missing product groups are skipped", "does not run atris"),
    ),
    (
        "atris-dump",
        "dump",
        ("standard output", "not modified"),
    ),
    (
        "nrlmsis2psf",
        "nrlmsis2psf",
        ("does not download atmosphere data",),
    ),
    ("psf2gdml", "psf2gdml", ("output defaults to the input basename",)),
    ("atrismacrogen", "atrismacrogen", ("refuses to overwrite",)),
    ("postprocess", "postprocess", ("does not gather chunk histograms",)),
)

MODERN_ENTRY_POINTS = tuple(
    (command, module_name)
    for command, module_name, _ in ENTRY_POINT_HELP
    if command.startswith("atris-")
)
LEGACY_ENTRY_POINTS = tuple(
    (command, module_name)
    for command, module_name, _ in ENTRY_POINT_HELP
    if not command.startswith("atris-")
)


@pytest.mark.parametrize(("command", "module_name", "expected"), ENTRY_POINT_HELP)
def test_entry_point_help_explains_scope(
    command, module_name, expected, monkeypatch, capsys
):
    module = importlib.import_module("atris_tools." + module_name)
    monkeypatch.setattr("sys.argv", [command, "--help"])

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.lower().split())
    assert help_text.startswith("usage: " + command)
    for text in expected:
        assert text in help_text


@pytest.mark.parametrize(("command", "module_name"), MODERN_ENTRY_POINTS)
def test_modern_entry_points_report_both_versions(
    command, module_name, monkeypatch, capsys
):
    module = importlib.import_module("atris_tools." + module_name)
    monkeypatch.setattr("sys.argv", [command, "--version"])
    monkeypatch.setattr(
        "atris_tools.version.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="AtRIS v3.1.0\n",
        ),
    )

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "AtRIS executable version (PEP 440): 3.1.0" in output
    assert "atris-tools version (PEP 440):" in output


@pytest.mark.parametrize(("command", "module_name"), LEGACY_ENTRY_POINTS)
def test_legacy_entry_points_do_not_advertise_version(
    command, module_name, monkeypatch, capsys
):
    module = importlib.import_module("atris_tools." + module_name)
    monkeypatch.setattr("sys.argv", [command, "--help"])

    with pytest.raises(SystemExit):
        module.main()

    assert "--version" not in capsys.readouterr().out
