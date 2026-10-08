"""Regression tests for the explicit AtRIS macro interface."""

import os
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
import pytest
import uproot

from atris_tools.atrismacrogen import macroGenManager
from atris_tools.gather import gather_simulation
from atris_tools.interface_output import read_root
from atris_tools.output_ntuples import (
    METADATA_SCHEMA,
    RESPONSE_SCHEMA,
    read_csv_ntuple,
)
from atris_tools.postprocess import process_run
from atris_tools.response_histograms import ResponseHistogramReader
from atris_tools.root_output import has_ntuple, read_ntuple
from atris_tools.run_chunks import run_chunks
from atris_tools.scatter import chunk_macro
from atris_tools.step_output import STEP_FIELDS, process_name

REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "minimal"
PHANTOMS = REPOSITORY_ROOT / "phantoms"
RESPONSE_STEM = "ramona_zero_0.060MeV_detA"
EXPECTED_HISTOGRAM_SUFFIXES = {
    "_h1_h1.1.csv",
    "_h2_h2.dir.csv",
    "_h2_h2.%s.dos.csv" % RESPONSE_STEM,
    "_h2_h2.%s.equi.csv" % RESPONSE_STEM,
    "_h2_h2.edep.csv",
    "_h2_h2.ion.csv",
    "_h2_h2.pos.csv",
    "_h2_h2.%s.rates.csv" % RESPONSE_STEM,
}
EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS = {
    "_h1_h1.1.csv",
    "_h2_h2.dir.csv",
    "_h2_h2.edep.csv",
    "_h2_h2.ion.csv",
    "_h2_h2.pos.csv",
}
EXPECTED_ROOT_HISTOGRAMS = {
    "h1.1",
    "h2.dir",
    "h2.%s.dos" % RESPONSE_STEM,
    "h2.edep",
    "h2.%s.equi" % RESPONSE_STEM,
    "h2.ion",
    "h2.pos",
    "h2.%s.rates" % RESPONSE_STEM,
}
EXPECTED_ROOT_METADATA = {
    "schema",
    "atris_version",
    "input_prefix",
    "physics_list",
    "output_mode",
    "phantom_count",
    "seeds_explicit",
    "random_seed_1",
    "random_seed_2",
}
EXPECTED_ROOT_RESPONSE_METADATA = {
    "phantom_stem",
    "name",
    "file",
    "scale_by_crossing_energy",
    "scale_by_radiation_weight",
    "scale_by_inverse_phantom_mass",
}


@pytest.fixture(scope="session")
def atris_command():
    command = shutil.which("AtRIS")
    if command is None:
        pytest.fail(
            "AtRIS is not on PATH; source atris/setup_atris.sh from the "
            "workspace root before running tests/regression"
        )
    return command


def source_macro(interface=False, events=2):
    fixture = "interface.mac" if interface else "ordinary.mac"
    lines = [
        line
        for line in (FIXTURE / fixture).read_text().splitlines()
        if not line.startswith("/random/setSeeds ")
        and not line.startswith("/run/beamOn ")
    ]
    lines.append("/run/beamOn %i" % events)
    return "\n".join(lines) + "\n"


def write_macro(
    run_directory,
    *,
    macro_name="protons.mac",
    geometry_file="planet.gdml",
    energy_bins_file="primary-energy.bins",
    output_file="protons",
    physics_list="FTFP_BERT_HP",
    output_mode="response",
    output_format="csv",
    phantom_files=None,
    direction_bins=(120, 60),
    position_bins=(120, 60),
    body=None,
):
    if phantom_files is None:
        phantom_files = [
            (
                RESPONSE_STEM,
                RESPONSE_STEM + "_response.txt",
                RESPONSE_STEM + "_counting.txt",
            )
        ]
    lines = [
        "/atris/geometryFile " + geometry_file,
        "/atris/energyBinsFile " + energy_bins_file,
        "/atris/outputStem " + output_file,
    ]
    for stem, response_file, counting_file in phantom_files:
        lines.append("/atris/phantom/name " + stem)
        for response_name, filename, factors in (
            ("dos", response_file, (True, False, True)),
            ("equi", response_file, (True, True, True)),
            ("rates", counting_file, (False, False, False)),
        ):
            lines.extend(
                (
                    "/atris/phantom/response/name " + response_name,
                    "/atris/phantom/response/tableFile " + filename,
                    "/atris/phantom/response/scaleByCrossingEnergy "
                    + str(factors[0]).lower(),
                    "/atris/phantom/response/scaleByRadiationWeight "
                    + str(factors[1]).lower(),
                    "/atris/phantom/response/scaleByInversePhantomMass "
                    + str(factors[2]).lower(),
                    "/atris/phantom/response/add",
                )
            )
    lines.extend(
        (
            "/atris/physicsList " + physics_list,
            "/atris/outputMode " + output_mode,
            "/atris/outputFormat " + output_format,
            "/atris/directionHistogram/azimuthBins %i" % direction_bins[0],
            "/atris/directionHistogram/cosineBins %i" % direction_bins[1],
            "/atris/positionHistogram/azimuthBins %i" % position_bins[0],
            "/atris/positionHistogram/cosineBins %i" % position_bins[1],
            "/atris/randomSeeds 123456 654321",
        )
    )
    macro = run_directory / macro_name
    macro.write_text("\n".join(lines) + "\n" + (body or source_macro()))
    return macro


def prepare_run(
    run_directory,
    *,
    interface=False,
    output_file="protons",
    output_mode="response",
    output_format="csv",
    phantom_count=1,
    events=2,
):
    geometry_fixture = "interface.gdml" if interface else "simulation.gdml"
    shutil.copyfile(FIXTURE / geometry_fixture, run_directory / "planet.gdml")
    shutil.copyfile(
        FIXTURE / "simulation.bins",
        run_directory / "primary-energy.bins",
    )

    phantom_files = []
    phantom_rows = []
    for phantom_id in range(phantom_count):
        stem = RESPONSE_STEM if phantom_id == 0 else "phantom-%i" % phantom_id
        response_file = stem + "_response.txt"
        counting_file = stem + "_counting.txt"
        shutil.copyfile(
            PHANTOMS / (RESPONSE_STEM + "_response.txt"),
            run_directory / response_file,
        )
        shutil.copyfile(
            PHANTOMS / (RESPONSE_STEM + "_counting.txt"),
            run_directory / counting_file,
        )
        phantom_files.append((stem, response_file, counting_file))
        phantom_rows.append("%s 1.0 1.0\n" % stem)
    if phantom_rows:
        (run_directory / "phantoms.txt").write_text("".join(phantom_rows))

    return write_macro(
        run_directory,
        output_file=output_file,
        output_mode=output_mode,
        output_format=output_format,
        phantom_files=phantom_files,
        body=source_macro(interface=interface, events=events),
    )


def replace_command(macro, command, replacement=None):
    lines = macro.read_text().splitlines()
    matching = [index for index, line in enumerate(lines) if line.startswith(command)]
    if len(matching) != 1:
        raise AssertionError("Expected one %s command" % command)
    if replacement is None:
        del lines[matching[0]]
    else:
        lines[matching[0]] = replacement
    macro.write_text("\n".join(lines) + "\n")


def invoke_atris(command, run_directory, *arguments, threads="1"):
    environment = os.environ.copy()
    environment["G4FORCENUMBEROFTHREADS"] = threads
    return subprocess.run(
        [command, *arguments],
        cwd=run_directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def run_atris(command, run_directory, macro_name="protons.mac", threads="1"):
    return invoke_atris(
        command,
        run_directory,
        macro_name,
        threads=threads,
    )


def histogram_entries(path):
    lines = path.read_text().splitlines()
    column_index = next(
        index for index, line in enumerate(lines) if not line.startswith("#")
    )
    data = np.atleast_2d(np.loadtxt(path, delimiter=",", skiprows=column_index + 1))
    return int(data[:, 0].sum())


def assert_timing_output(output, worker_threads):
    match = re.search(
        r"### AtRIS timing: Geant4 macro wall time: (\d+\.\d{3}) s "
        r"using (\d+) worker thread\(s\)\n"
        r"### AtRIS timing: setup/cleanup wall time: (\d+\.\d{3}) s\n"
        r"### AtRIS timing: total wall time: (\d+\.\d{3}) s",
        output,
    )
    assert match is not None
    macro_seconds, reported_workers, outside_seconds, total_seconds = match.groups()
    assert int(reported_workers) == worker_threads
    assert float(macro_seconds) >= 0
    assert float(outside_seconds) >= 0
    assert float(total_seconds) == pytest.approx(
        float(macro_seconds) + float(outside_seconds),
        abs=0.002,
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    ("output_mode", "output_format", "creates_root", "creates_steps"),
    [
        pytest.param("response", "csv", False, False, id="csv-response"),
        pytest.param("profile", "csv", False, False, id="csv-profile"),
        pytest.param("response", "root", True, False, id="root-response"),
        pytest.param("profile", "root", True, False, id="root-profile"),
        pytest.param("shower", "root", True, True, id="root-shower"),
    ],
)
def test_macro_runs_one_worker_and_writes_expected_histograms(
    tmp_path,
    atris_command,
    output_mode,
    output_format,
    creates_root,
    creates_steps,
):
    prepare_run(
        tmp_path,
        output_mode=output_mode,
        output_format=output_format,
    )

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: executing macro protons.mac" in result.stdout
    assert "### AtRIS: Starting the simulation" in result.stdout
    assert "### AtRIS: simulation used 1 worker thread(s)" in result.stdout
    assert "### AtRIS: the simulation has completed" in result.stdout
    assert_timing_output(result.stdout, 1)
    if output_mode == "profile":
        assert "### AtRIS: profile mode writes" in result.stdout
    if output_mode == "shower":
        assert "### AtRIS: shower mode writes" in result.stdout

    root_path = tmp_path / "protons.root"
    assert root_path.exists() is creates_root
    if creates_root:
        assert not list(tmp_path.glob("protons_*.csv"))
        with uproot.open(root_path) as root_file:
            object_names = set(root_file.keys(cycle=False))
            expected_objects = set(EXPECTED_ROOT_HISTOGRAMS)
            expected_objects.update(("metadata", "responses"))
            if output_mode in ("profile", "shower"):
                expected_objects.add("interfaces")
            if creates_steps:
                expected_objects.add("steps")
            assert object_names == expected_objects
            assert int(root_file["h1.1"].member("fEntries")) == 2
            metadata = root_file["metadata"]
            assert set(metadata.keys()) == EXPECTED_ROOT_METADATA
            assert metadata.num_entries == 1
            assert metadata["schema"].array(library="np").tolist() == [2]
            assert metadata["output_mode"].array(library="np").tolist() == [output_mode]
            assert metadata["phantom_count"].array(library="np").tolist() == [1]
            responses = root_file["responses"]
            assert set(responses.keys()) == EXPECTED_ROOT_RESPONSE_METADATA
            assert responses.num_entries == 3
            assert responses["name"].array(library="np").tolist() == [
                "dos",
                "equi",
                "rates",
            ]
            assert responses["scale_by_crossing_energy"].array(
                library="np"
            ).tolist() == [1, 1, 0]
            assert responses["scale_by_radiation_weight"].array(
                library="np"
            ).tolist() == [0, 1, 0]
            assert responses["scale_by_inverse_phantom_mass"].array(
                library="np"
            ).tolist() == [1, 1, 0]
    else:
        written_suffixes = {
            path.name[len("protons") :] for path in tmp_path.glob("protons_h*.csv")
        }
        assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES
        assert histogram_entries(tmp_path / "protons_h1_h1.1.csv") == 2
        metadata = read_csv_ntuple(tmp_path / "protons", "metadata", METADATA_SCHEMA)
        assert set(metadata) == EXPECTED_ROOT_METADATA
        assert metadata["schema"].tolist() == [2]
        assert metadata["input_prefix"].tolist() == ["planet"]
        assert metadata["physics_list"].tolist() == ["FTFP_BERT_HP"]
        assert metadata["output_mode"].tolist() == [output_mode]
        assert metadata["random_seed_1"].tolist() == [123456]
        assert metadata["random_seed_2"].tolist() == [654321]
        responses = read_csv_ntuple(tmp_path / "protons", "responses", RESPONSE_SCHEMA)
        assert set(responses) == EXPECTED_ROOT_RESPONSE_METADATA
        assert responses["name"].tolist() == ["dos", "equi", "rates"]
        assert responses["scale_by_crossing_energy"].tolist() == [1, 1, 0]
        assert responses["scale_by_radiation_weight"].tolist() == [0, 1, 0]
        assert responses["scale_by_inverse_phantom_mass"].tolist() == [1, 1, 0]

    with ResponseHistogramReader(tmp_path / "protons") as histograms:
        total_deposition = histograms.values("h2.edep")
        ionization = histograms.values("h2.ion")
        assert np.all(total_deposition + 1e-12 >= ionization)
        for name in ("h2.dir", "h2.pos"):
            np.testing.assert_allclose(
                histograms.axes(name)[1][[0, -1]],
                [-1.0, 1.0],
            )
            values = histograms.values(name)
            assert values.sum() == values[1:-1, 1:-1].sum() == 2


@pytest.mark.regression
def test_macro_paths_do_not_have_to_share_a_prefix(tmp_path, atris_command):
    prepare_run(tmp_path, output_file="named-result")
    (tmp_path / "protons.mac").rename(tmp_path / "study.mac")

    result = run_atris(atris_command, tmp_path, "study.mac")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "named-result_h1_h1.1.csv").is_file()


@pytest.mark.regression
def test_generated_macro_runs_directly(tmp_path, atris_command):
    shutil.copyfile(FIXTURE / "simulation.psf", tmp_path / "simulation.psf")
    shutil.copyfile(FIXTURE / "simulation.gdml", tmp_path / "simulation.gdml")
    macroGenManager(
        1,
        output_dir=tmp_path,
        random_seed=12345,
        energy_points=2,
    )

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "protons_h1_h1.1.csv").is_file()


@pytest.mark.regression
def test_spherical_source_populates_both_angular_hemispheres(
    tmp_path,
    atris_command,
):
    prepare_run(tmp_path)
    body = (
        "/atris/initialize\n"
        "/gps/particle proton\n"
        "/gps/ene/mono 10 MeV\n"
        "/gps/pos/type Surface\n"
        "/gps/pos/shape Sphere\n"
        "/gps/pos/centre 0 0 0 mm\n"
        "/gps/pos/radius 3 km\n"
        "/gps/ang/type cos\n"
        "/gps/ang/mintheta 0 deg\n"
        "/gps/ang/maxtheta 90 deg\n"
        "/run/beamOn 100\n"
    )
    write_macro(tmp_path, body=body)

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    with ResponseHistogramReader(tmp_path / "protons") as histograms:
        for name in ("h2.dir", "h2.pos"):
            values = histograms.values(name)
            interior = values[1:-1, 1:-1]
            assert values.sum() == interior.sum() == 100
            assert interior[:, :30].sum() > 0
            assert interior[:, 30:].sum() > 0


@pytest.mark.regression
def test_unsupported_output_format_fails_cleanly(tmp_path, atris_command):
    prepare_run(tmp_path, output_format="unsupported")

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert not list(tmp_path.glob("protons_*.csv"))
    assert not (tmp_path / "protons.root").exists()


@pytest.mark.regression
def test_profile_mode_writes_merged_root_interface_ntuple(
    tmp_path,
    atris_command,
):
    prepare_run(
        tmp_path,
        interface=True,
        output_mode="profile",
        output_format="root",
    )

    result = run_atris(atris_command, tmp_path, threads="2")

    assert result.returncode == 0, result.stdout + result.stderr
    root_path = tmp_path / "protons.root"
    assert root_path.is_file()
    assert len(read_root(root_path)) == 2
    assert has_ntuple(root_path, "interfaces")
    assert not has_ntuple(root_path, "steps")
    assert not list(tmp_path.glob("protons_t*.root"))


@pytest.mark.regression
def test_shower_mode_writes_root_steps_with_track_genealogy(
    tmp_path,
    atris_command,
):
    prepare_run(tmp_path, output_mode="shower", output_format="root")

    result = run_atris(atris_command, tmp_path, threads="2")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: simulation used 2 worker thread(s)" in result.stdout
    assert_timing_output(result.stdout, 2)
    records = read_ntuple(tmp_path / "protons.root", "steps", STEP_FIELDS)
    assert len(records)
    assert set(records["event_id"]) == {0, 1}
    assert np.all(records["track_id"] > 0)
    assert np.all(records["step_id"] > 0)
    assert all(process_name(value) for value in records["creator_process"])
    assert all(process_name(value) for value in records["step_process"])
    assert not list(tmp_path.glob("protons_t*.root"))


@pytest.mark.regression
def test_shower_mode_contains_profile_interface_records(tmp_path, atris_command):
    profile = tmp_path / "profile"
    shower = tmp_path / "shower"
    profile.mkdir()
    shower.mkdir()
    prepare_run(
        profile,
        interface=True,
        output_mode="profile",
        output_format="root",
    )
    prepare_run(
        shower,
        interface=True,
        output_mode="shower",
        output_format="root",
    )

    profile_result = run_atris(atris_command, profile)
    shower_result = run_atris(atris_command, shower)

    assert profile_result.returncode == 0, profile_result.stdout + profile_result.stderr
    assert shower_result.returncode == 0, shower_result.stdout + shower_result.stderr
    np.testing.assert_array_equal(
        read_root(profile / "protons.root"),
        read_root(shower / "protons.root"),
    )


@pytest.mark.regression
def test_chunk_runner_supplies_output_and_seeds_to_shared_macro(
    tmp_path,
    atris_command,
    monkeypatch,
):
    macro = prepare_run(
        tmp_path,
        output_mode="profile",
        output_format="root",
        events=1,
    )
    contents, _, _ = chunk_macro(macro, chunks=1)
    (tmp_path / "protons.chunk.mac").write_text(contents)
    (tmp_path / "chunks").mkdir()
    (tmp_path / "chunks.txt").write_text("protons 123456 654321\n")
    monkeypatch.setenv("G4FORCENUMBEROFTHREADS", "1")

    assert run_chunks(tmp_path, entry=1) == 1

    output = tmp_path / "chunks" / "protons_123456_654321.root"
    assert output.is_file()
    assert (tmp_path / "chunks" / "protons_123456_654321.COMPLETE").is_file()
    with uproot.open(output) as root_file:
        metadata = root_file["metadata"]
        assert metadata["output_mode"].array(library="np").tolist() == ["profile"]
        assert metadata["random_seed_1"].array(library="np").tolist() == [123456]
        assert metadata["random_seed_2"].array(library="np").tolist() == [654321]


@pytest.mark.regression
def test_csv_and_root_response_histograms_gather_equivalently(
    tmp_path,
    atris_command,
):
    outputs = {}
    response_definitions = {}
    entry = ("protons", "123456", "654321")
    run_name = "protons_123456_654321"
    for output_format in ("csv", "root"):
        run_directory = tmp_path / output_format
        run_directory.mkdir()
        (run_directory / "chunks").mkdir()
        shutil.copyfile(FIXTURE / "simulation.psf", run_directory / "simulation.psf")
        prepare_run(
            run_directory,
            output_file="chunks/" + run_name,
            output_format=output_format,
            events=1,
        )

        result = run_atris(atris_command, run_directory)
        assert result.returncode == 0, result.stdout + result.stderr
        (run_directory / "chunks" / (run_name + ".COMPLETE")).touch()
        gather_simulation(run_directory, [entry], "protons")
        if output_format == "root":
            (run_directory / "protons.mac").unlink()

        with ResponseHistogramReader(run_directory / "protons") as histograms:
            response_definitions[output_format] = histograms.response_definitions()
            outputs[output_format] = {
                name: (histograms.axes(name), histograms.values(name))
                for name in histograms.names()
            }

    assert outputs["csv"].keys() == outputs["root"].keys()
    for name in outputs["csv"]:
        csv_axes, csv_data = outputs["csv"][name]
        root_axes, root_data = outputs["root"][name]
        for csv_axis, root_axis in zip(csv_axes, root_axes):
            np.testing.assert_allclose(csv_axis, root_axis, rtol=1e-6)
        np.testing.assert_allclose(csv_data, root_data)
    assert response_definitions["csv"] == response_definitions["root"]


@pytest.mark.regression
def test_version_form_reports_version_without_simulation_inputs(
    tmp_path,
    atris_command,
):
    result = invoke_atris(atris_command, tmp_path, "--version")

    assert result.returncode == 0
    assert re.fullmatch(r"AtRIS \S+\n", result.stdout)
    assert result.stderr == ""


@pytest.mark.regression
@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param((), id="no-arguments"),
        pytest.param(("protons.mac", "extra"), id="too-many-arguments"),
    ],
)
def test_wrong_argument_count_returns_failure(tmp_path, atris_command, arguments):
    result = invoke_atris(atris_command, tmp_path, *arguments)

    assert result.returncode != 0
    assert "Usage:" in result.stderr
    assert "<macro-file>" in result.stderr


@pytest.mark.regression
@pytest.mark.parametrize(
    "physics_list",
    ["NOT_A_GEANT4_PHYSICS_LIST", "FTFP_BERT_HPjunk"],
)
def test_unsupported_physics_list_exits_nonzero(
    tmp_path,
    atris_command,
    physics_list,
):
    prepare_run(tmp_path)
    replace_command(
        tmp_path / "protons.mac",
        "/atris/physicsList ",
        "/atris/physicsList " + physics_list,
    )

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert "requested physics list " + physics_list in result.stdout + result.stderr
    assert "NOT available" in result.stdout + result.stderr
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
def test_repeated_configuration_uses_last_value(tmp_path, atris_command):
    macro = prepare_run(tmp_path)
    text = macro.read_text()
    for final, earlier in (
        ("/atris/geometryFile planet.gdml", "/atris/geometryFile missing.gdml"),
        (
            "/atris/energyBinsFile primary-energy.bins",
            "/atris/energyBinsFile missing.bins",
        ),
        ("/atris/outputStem protons", "/atris/outputStem superseded"),
        ("/atris/randomSeeds 123456 654321", "/atris/randomSeeds 111111 222222"),
        (
            "/atris/physicsList QGSP_BERT",
            "/atris/physicsList NOT_A_GEANT4_PHYSICS_LIST",
        ),
        ("/atris/outputMode response", "/atris/outputMode shower"),
        ("/atris/outputFormat csv", "/atris/outputFormat unsupported"),
    ):
        if final == "/atris/physicsList QGSP_BERT":
            text = text.replace("/atris/physicsList FTFP_BERT_HP", final)
        text = text.replace(final, earlier + "\n" + final)
    macro.write_text(text)

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    metadata = read_csv_ntuple(tmp_path / "protons", "metadata", METADATA_SCHEMA)
    assert metadata["input_prefix"].tolist() == ["planet"]
    assert metadata["physics_list"].tolist() == ["QGSP_BERT"]
    assert metadata["output_mode"].tolist() == ["response"]
    assert metadata["random_seed_1"].tolist() == [123456]
    assert metadata["random_seed_2"].tolist() == [654321]
    assert not list(tmp_path.glob("superseded*"))


@pytest.mark.regression
def test_macro_uses_cpp_configuration_defaults(tmp_path, atris_command):
    macro = prepare_run(tmp_path)
    (tmp_path / "planet.gdml").rename(tmp_path / "simulation.gdml")
    (tmp_path / "primary-energy.bins").rename(tmp_path / "simulation.bins")
    for command in (
        "/atris/geometryFile ",
        "/atris/energyBinsFile ",
        "/atris/physicsList ",
        "/atris/outputMode ",
        "/atris/outputFormat ",
    ):
        replace_command(macro, command)

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    metadata = read_csv_ntuple(tmp_path / "protons", "metadata", METADATA_SCHEMA)
    assert metadata["input_prefix"].tolist() == ["simulation"]
    assert metadata["physics_list"].tolist() == ["FTFP_BERT_HP"]
    assert metadata["output_mode"].tolist() == ["response"]


@pytest.mark.regression
def test_macro_requires_output_stem(tmp_path, atris_command):
    macro = prepare_run(tmp_path)
    replace_command(macro, "/atris/outputStem ")

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert "AtRIS initialization requires outputStem" in result.stdout + result.stderr


@pytest.mark.regression
def test_macro_configures_source_histogram_bins(tmp_path, atris_command):
    prepare_run(tmp_path)
    replace_command(
        tmp_path / "protons.mac",
        "/atris/directionHistogram/azimuthBins ",
        "/atris/directionHistogram/azimuthBins 12",
    )
    replace_command(
        tmp_path / "protons.mac",
        "/atris/directionHistogram/cosineBins ",
        "/atris/directionHistogram/cosineBins 6",
    )
    replace_command(
        tmp_path / "protons.mac",
        "/atris/positionHistogram/azimuthBins ",
        "/atris/positionHistogram/azimuthBins 10",
    )
    replace_command(
        tmp_path / "protons.mac",
        "/atris/positionHistogram/cosineBins ",
        "/atris/positionHistogram/cosineBins 5",
    )

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    with ResponseHistogramReader(tmp_path / "protons") as histograms:
        assert [len(axis) - 1 for axis in histograms.axes("h2.dir")] == [12, 6]
        assert [len(axis) - 1 for axis in histograms.axes("h2.pos")] == [10, 5]


@pytest.mark.regression
def test_macro_rejects_nonpositive_source_histogram_bins(
    tmp_path,
    atris_command,
):
    prepare_run(tmp_path)
    replace_command(
        tmp_path / "protons.mac",
        "/atris/directionHistogram/azimuthBins ",
        "/atris/directionHistogram/azimuthBins 0",
    )

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
@pytest.mark.parametrize(
    "macro_contents",
    [
        pytest.param(None, id="missing-macro"),
        pytest.param("/not/an/atris/command\n", id="invalid-macro-command"),
    ],
)
def test_missing_or_invalid_macro_exits_nonzero(
    tmp_path,
    atris_command,
    macro_contents,
):
    prepare_run(tmp_path)
    macro = tmp_path / "protons.mac"
    if macro_contents is None:
        macro.unlink()
    else:
        macro.write_text(macro_contents)

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert "### AtRIS: macro execution failed with Geant4 status" in result.stderr
    assert "### AtRIS: the simulation has completed" not in result.stdout


@pytest.mark.regression
@pytest.mark.parametrize(
    "filename",
    ["planet.gdml", "primary-energy.bins"],
)
def test_missing_explicit_input_file_exits_nonzero(
    tmp_path,
    atris_command,
    filename,
):
    prepare_run(tmp_path)
    (tmp_path / filename).unlink()

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert filename in result.stdout + result.stderr
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
def test_zero_phantoms_runs_without_phantom_histograms(tmp_path, atris_command):
    prepare_run(tmp_path, phantom_count=0)

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    written_suffixes = {
        path.name[len("protons") :] for path in tmp_path.glob("protons_h*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS


@pytest.mark.regression
def test_macro_loads_each_explicit_phantom(tmp_path, atris_command):
    prepare_run(tmp_path, phantom_count=2)

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "for phantom '%s'" % RESPONSE_STEM in result.stdout
    assert "for phantom 'phantom-1'" in result.stdout
    assert (tmp_path / "protons_h2_h2.phantom-1.dos.csv").is_file()


@pytest.mark.regression
@pytest.mark.parametrize("suffix", ["response", "counting"])
def test_missing_explicit_phantom_file_exits_nonzero(
    tmp_path,
    atris_command,
    suffix,
):
    prepare_run(tmp_path)
    filename = RESPONSE_STEM + "_" + suffix + ".txt"
    (tmp_path / filename).unlink()

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert filename in result.stdout + result.stderr
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
def test_macro_accepts_an_additional_named_response(tmp_path, atris_command):
    macro = prepare_run(tmp_path)
    extra = RESPONSE_STEM + "_bounting.txt"
    shutil.copyfile(tmp_path / (RESPONSE_STEM + "_counting.txt"), tmp_path / extra)
    macro.write_text(
        macro.read_text().replace(
            "/atris/physicsList ",
            "/atris/phantom/name %s\n"
            "/atris/phantom/response/name bounting\n"
            "/atris/phantom/response/tableFile %s\n"
            "/atris/phantom/response/scaleByCrossingEnergy false\n"
            "/atris/phantom/response/scaleByRadiationWeight false\n"
            "/atris/phantom/response/scaleByInversePhantomMass false\n"
            "/atris/phantom/response/add\n"
            "/atris/physicsList " % (RESPONSE_STEM, extra),
        )
    )

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / ("protons_h2_h2.%s.bounting.csv" % RESPONSE_STEM)).is_file()


@pytest.mark.regression
def test_repeated_response_identity_uses_last_definition(tmp_path, atris_command):
    macro = prepare_run(tmp_path)
    replacement = (
        "/atris/phantom/name %s\n"
        "/atris/phantom/response/name dos\n"
        "/atris/phantom/response/tableFile %s_counting.txt\n"
        "/atris/phantom/response/scaleByCrossingEnergy false\n"
        "/atris/phantom/response/scaleByRadiationWeight false\n"
        "/atris/phantom/response/scaleByInversePhantomMass false\n"
        "/atris/phantom/response/add\n"
        "/atris/physicsList "
    ) % (RESPONSE_STEM, RESPONSE_STEM)
    macro.write_text(macro.read_text().replace("/atris/physicsList ", replacement))

    result = run_atris(atris_command, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    responses = read_csv_ntuple(tmp_path / "protons", "responses", RESPONSE_SCHEMA)
    dos = responses["name"] == "dos"
    assert responses["file"][dos].tolist() == [RESPONSE_STEM + "_counting.txt"]
    assert responses["scale_by_crossing_energy"][dos].tolist() == [0]
    assert responses["scale_by_inverse_phantom_mass"][dos].tolist() == [0]


@pytest.mark.regression
def test_macro_rejects_an_incomplete_phantom_response(tmp_path, atris_command):
    macro = prepare_run(tmp_path)
    macro.write_text(
        macro.read_text().replace(
            "/atris/phantom/response/tableFile %s_response.txt\n" % RESPONSE_STEM,
            "",
            1,
        )
    )

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert "/atris/phantom/response/tableFile" in result.stdout + result.stderr


@pytest.mark.regression
@pytest.mark.parametrize("output_format", ["csv", "root"])
def test_postprocess_writes_stem_named_phantom_outputs(
    tmp_path,
    monkeypatch,
    atris_command,
    output_format,
):
    prepare_run(tmp_path, interface=True, output_format=output_format)
    psf = (FIXTURE / "simulation.psf").read_text()
    psf += (
        "2.000000 3.000000 0.000000 6.283185 0.000000 3.141593 "
        "2 293.150000 1.000000e-25 1.000000e-10 1.000000 0.000000\n"
    )
    (tmp_path / "simulation.psf").write_text(psf)
    result = run_atris(atris_command, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    if output_format == "root":
        (tmp_path / "protons.mac").unlink()
    monkeypatch.chdir(tmp_path)

    process_run("protons")

    for response_name in ("dose", "equi", "rates"):
        assert Path("protons.%s.%s" % (RESPONSE_STEM, response_name)).is_file()
    assert not list(tmp_path.glob("protons.dose*"))
    assert not list(tmp_path.glob("protons.equi*"))
    assert not list(tmp_path.glob("protons.rates*"))


@pytest.mark.regression
@pytest.mark.parametrize("file_type", ["response", "counting"])
def test_mismatched_phantom_pdg_headers_exit_nonzero(
    tmp_path,
    atris_command,
    file_type,
):
    prepare_run(tmp_path, phantom_count=2)
    path = tmp_path / ("phantom-1_" + file_type + ".txt")
    lines = path.read_text().splitlines()
    lines[0] = " ".join(lines[0].split()[:-1])
    path.write_text("\n".join(lines) + "\n")

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert "### AtRIS: PDG header mismatch:" in result.stderr
    assert path.name in result.stderr
    assert RESPONSE_STEM + "_response.txt" in result.stderr
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
@pytest.mark.parametrize("file_type", ["response", "counting"])
def test_incomplete_phantom_response_table_exits_nonzero(
    tmp_path,
    atris_command,
    file_type,
):
    prepare_run(tmp_path)
    path = tmp_path / (RESPONSE_STEM + "_" + file_type + ".txt")
    lines = path.read_text().splitlines()
    lines[-1] = " ".join(lines[-1].split()[:-1])
    path.write_text("\n".join(lines) + "\n")

    result = run_atris(atris_command, tmp_path)

    assert result.returncode != 0
    assert "response value count mismatch in " + path.name in result.stderr
    assert not list(tmp_path.glob("protons_*.csv"))
