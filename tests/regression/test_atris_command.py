"""Characterize the observable AtRIS command-line contract.

Tests whose names contain ``currently`` record permissive behavior in the
existing executable; they do not imply that the behavior is desirable.
"""

import os
from contextlib import nullcontext
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
import pytest
import uproot

from atris_tools.root_records import read_interface_records
from atris_tools.gather import gather_simulation
from atris_tools.histogram import ResponseHistogramReader
from atris_tools.root_records import has_ntuple, read_ntuple
from atris_tools.root_records import STEP_FIELDS, process_name


REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "minimal"
PHANTOMS = REPOSITORY_ROOT / "phantoms"
EXPECTED_HISTOGRAM_SUFFIXES = {
    "_h1_h1.1.csv",
    "_h2_h2.dir.csv",
    "_h2_h2.dos0.csv",
    "_h2_h2.equi0.csv",
    "_h2_h2.edep.csv",
    "_h2_h2.ion.csv",
    "_h2_h2.pos.csv",
    "_h2_h2.rates0.csv",
    "_h2_h2.ion.primary.csv",
    "_h2_h2.edep.primary.csv",
    "_h2_h2.dos0.primary.csv",
    "_h2_h2.equi0.primary.csv",
    "_h2_h2.rates0.primary.csv",
}
EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS = {
    "_h1_h1.1.csv",
    "_h2_h2.dir.csv",
    "_h2_h2.edep.csv",
    "_h2_h2.ion.csv",
    "_h2_h2.pos.csv",
    "_h2_h2.ion.primary.csv",
    "_h2_h2.edep.primary.csv",
}
EXPECTED_ROOT_HISTOGRAMS = {
    "h1.1",
    "h2.dir",
    "h2.dos0",
    "h2.edep",
    "h2.equi0",
    "h2.ion",
    "h2.pos",
    "h2.rates0",
    "h2.ion.primary",
    "h2.edep.primary",
    "h2.dos0.primary",
    "h2.equi0.primary",
    "h2.rates0.primary",
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


@pytest.fixture(scope="session")
def atris_command():
    command = shutil.which("AtRIS")
    if command is None:
        pytest.fail(
            "AtRIS is not on PATH; source atris/setup_atris.sh from the "
            "workspace root before running tests/regression"
        )
    return command


def prepare_run(run_directory, *, chunked=False):
    shutil.copyfile(FIXTURE / "simulation.gdml", run_directory / "protons.gdml")
    shutil.copyfile(FIXTURE / "simulation.bins", run_directory / "protons.bins")
    shutil.copyfile(FIXTURE / "ordinary.mac", run_directory / "protons.mac")
    shutil.copyfile(
        PHANTOMS / "ramona_zero_0.060MeV_detA_old_response.txt",
        run_directory / "radiation_phantom0.txt",
    )
    shutil.copyfile(
        PHANTOMS / "ramona_zero_0.060MeV_detA_counting.txt",
        run_directory / "counting_phantom0.txt",
    )
    if chunked:
        shutil.copyfile(FIXTURE / "chunk.mac", run_directory / "protons.chunk.mac")
        (run_directory / "chunks").mkdir()

def prepare_interface_run(run_directory):
    prepare_run(run_directory)
    shutil.copyfile(FIXTURE / "interface.gdml", run_directory / "protons.gdml")
    shutil.copyfile(FIXTURE / "interface.mac", run_directory / "protons.mac")


@pytest.mark.regression
def test_untagged_response_coefficients_scale_dose(tmp_path, atris_command):
    histograms = []
    for scale in (1.0, 0.5):
        directory = tmp_path / str(scale)
        directory.mkdir()
        prepare_interface_run(directory)
        path = directory / "radiation_phantom0.txt"
        pdgs = np.loadtxt(path, max_rows=1, dtype=int)
        coefficients = np.loadtxt(path, skiprows=1)
        np.savetxt(
            path, coefficients * scale, header=" ".join(map(str, pdgs)), comments=""
        )
        result = run_atris(atris_command, directory, "protons.root")
        assert result.returncode == 0, result.stdout + result.stderr
        with uproot.open(directory / "protons.root") as root:
            histograms.append(
                {name: root[name].values() for name in ("h2.dos0", "h2.equi0", "h2.rates0")}
            )
    assert np.sum(histograms[0]["h2.dos0"]) > 0
    for name in ("h2.dos0", "h2.equi0"):
        np.testing.assert_allclose(
            histograms[1][name], histograms[0][name] * 0.5, rtol=1e-12
        )
    np.testing.assert_array_equal(histograms[0]["h2.rates0"], histograms[1]["h2.rates0"])


@pytest.mark.regression
def test_phantom_comments_leave_transport_results_unchanged(tmp_path, atris_command):
    results = []
    for annotated in (False, True):
        directory = tmp_path / str(annotated)
        directory.mkdir()
        prepare_interface_run(directory)
        if annotated:
            for name in ("radiation_phantom0.txt", "counting_phantom0.txt"):
                path = directory / name
                lines = path.read_text().splitlines(keepends=True)
                lines[0] = lines[0].rstrip("\n") + " # PDG particle codes.\n"
                lines.insert(2, "# Comments may also appear between particle rows.\n")
                path.write_text(
                    "\n  # Material and geometry documentation.\n\n" + "".join(lines)
                )
        result = run_atris(atris_command, directory, "protons.root")
        assert result.returncode == 0, result.stdout + result.stderr
        with uproot.open(directory / "protons.root") as root:
            results.append({name: root[name].values() for name in
                            ("h2.dos0", "h2.equi0", "h2.rates0")})
    for name in results[0]:
        np.testing.assert_array_equal(results[0][name], results[1][name])


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


def run_atris(
    command,
    run_directory,
    simulation,
    *,
    physics="FTFP_BERT_HP",
    mode="-1",
    phantom_count="1",
    threads="1",
):
    return invoke_atris(
        command,
        run_directory,
        physics,
        simulation,
        str(mode),
        str(phantom_count),
        threads=threads,
    )


def histogram_entries(path):
    lines = path.read_text().splitlines()
    column_index = next(
        index for index, line in enumerate(lines) if not line.startswith("#")
    )
    data = np.atleast_2d(
        np.loadtxt(path, delimiter=",", skiprows=column_index + 1)
    )
    return int(data[:, 0].sum())


def histogram_annotations(path):
    return {
        fields[1]: fields[2]
        for line in path.read_text().splitlines()
        if line.startswith("#annotation ")
        for fields in [line.split(" ", 2)]
    }


@pytest.mark.regression
@pytest.mark.parametrize("output,threads", [("root", "1"), ("csv", "2")])
@pytest.mark.parametrize("energy", [0.1, 10, 1000])
@pytest.mark.parametrize("particle,radiation_weight", [("proton", 2), ("alpha", 20)])
def test_primary_moments_combine_both_sides_of_an_interface(
    tmp_path, atris_command, output, threads, energy, particle, radiation_weight
):
    from atris_tools.gdml import psf_to_gdml
    from atris_tools.psf import PSF

    prepare_run(tmp_path)
    psf = PSF(inner_radius_km=[0, 1, 2, 3.5], outer_radius_km=[1, 2, 3, 4],
              temperature_k=293, pressure_pa=0, density_g_cm3=1e-25,
              mass_fractions={"H": 1})
    psf_to_gdml(psf.save(tmp_path / "protons.psf"), tmp_path / "protons.gdml")
    for index, scale in enumerate((1, 0.5)):
        for kind in ("radiation", "counting"):
            source = tmp_path / f"{kind}_phantom0.txt"
            pdgs = np.loadtxt(source, max_rows=1, dtype=int)
            coefficients = np.loadtxt(source, skiprows=1)
            np.savetxt(tmp_path / f"{kind}_phantom{index}.txt",
                       np.full_like(coefficients, scale),
                       header=" ".join(map(str, pdgs)), comments="")
    # A chord misses the core, crossing the same interface inward and outward
    # through two different sensitive volumes. No material interactions occur.
    (tmp_path / "protons.mac").write_text(
        f"/run/initialize\n/gps/particle {particle}\n/gps/ene/mono {energy} MeV\n"
        "/gps/pos/type Point\n/gps/pos/centre 3 1.5 0 km\n/gps/direction -1 0 0\n"
        "/random/setSeeds 123456 654321\n/run/beamOn 4\n")
    result = run_atris(atris_command, tmp_path, "protons." + output,
                       phantom_count="2", threads=threads)
    assert result.returncode == 0, result.stdout + result.stderr
    with ResponseHistogramReader(tmp_path / "protons") as reader:
        assert reader.phantom_count() == 2
        primary = reader["h1.1"]
        energy_bin = np.searchsorted(primary.axes[0], energy, side="right")
        assert primary.values[energy_bin] == 4
        for index, scale in enumerate((1, 0.5)):
            for kind, weight in (("dos", energy * 1e6),
                                 ("equi", energy * 1e6 * radiation_weight), ("rates", 1)):
                name = f"h2.{kind}{index}"
                original, companion = reader[name], reader[name + ".primary"]
                interface_bin = np.searchsorted(original.axes[1], 1, side="right")
                bin_index = energy_bin, interface_bin
                assert original.values[bin_index] == pytest.approx(8 * scale * weight)
                assert original.sumw2[bin_index] == pytest.approx(8 * (scale * weight)**2)
                assert companion.sumw2[bin_index] == pytest.approx(16 * (scale * weight)**2)
                np.testing.assert_allclose(companion.values, original.values)
                with (pytest.warns(RuntimeWarning, match="CSV rounding")
                      if output == "csv" else nullcontext()):
                    variance = reader.mean_variance(name)
                np.testing.assert_allclose(variance[energy_bin], 0, atol=1e-12)
                assert np.isnan(variance[primary.values == 0]).all()


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
    ("simulation", "mode", "creates_root", "creates_steps"),
    [
        pytest.param("protons", "-1", False, False, id="default-csv-response"),
        pytest.param("protons.csv", "-1", False, False, id="explicit-csv-response"),
        pytest.param("protons.csv", "0", False, False, id="csv-interface"),
        pytest.param("protons.root", "-1", True, False, id="root-response"),
        pytest.param("protons.root", "0", True, False, id="root-interface"),
        pytest.param("protons.root", "1", True, True, id="root-shower"),
    ],
)
def test_ordinary_prefix_runs_one_worker_and_writes_expected_histograms(
    tmp_path, atris_command, simulation, mode, creates_root, creates_steps
):
    prepare_run(tmp_path)

    result = run_atris(atris_command, tmp_path, simulation, mode=mode)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: executing macro protons.mac" in result.stdout
    assert "### AtRIS: Starting the simulation" in result.stdout
    assert "### AtRIS: simulation used 1 worker thread(s)" in result.stdout
    assert "### AtRIS: the simulation has completed" in result.stdout
    assert_timing_output(result.stdout, 1)

    root_path = tmp_path / "protons.root"
    assert root_path.exists() is creates_root
    if creates_root:
        assert not list(tmp_path.glob("protons_*.csv"))
        with uproot.open(root_path) as root_file:
            object_names = set(root_file.keys(cycle=False))
            expected_objects = set(EXPECTED_ROOT_HISTOGRAMS)
            if mode in ("0", "1"):
                expected_objects.update(("metadata", "interfaces"))
            if creates_steps:
                expected_objects.add("steps")
            assert object_names == expected_objects
            assert int(root_file["h1.1"].member("fEntries")) == 2
            if mode in ("0", "1"):
                metadata = root_file["metadata"]
                assert set(metadata.keys()) == EXPECTED_ROOT_METADATA
                assert metadata.num_entries == 1
                assert metadata["output_mode"].array(library="np").tolist() == [
                    int(mode)
                ]
                assert metadata["phantom_count"].array(library="np").tolist() == [1]
    else:
        written_suffixes = {
            path.name[len("protons"):]
            for path in tmp_path.glob("protons_h*.csv")
        }
        assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES
        assert histogram_entries(tmp_path / "protons_h1_h1.1.csv") == 2
        for path in tmp_path.glob("protons_h*.csv"):
            annotations = histogram_annotations(path)
            assert annotations["atris.csv_schema"] == "1"
            assert annotations["atris.input_prefix"] == "protons"
            assert annotations["atris.physics_list"] == "FTFP_BERT_HP"
            assert annotations["atris.output_mode"] == mode
            assert annotations["atris.random_seed_pairs"] == "runtime-default"
            assert annotations["atris.quantity"]

    with ResponseHistogramReader(tmp_path / "protons") as histograms:
        total_deposition = histograms["h2.edep"].values
        ionization = histograms["h2.ion"].values
        assert np.all(total_deposition + 1e-12 >= ionization)
        for name in ("h2.dir", "h2.pos"):
            np.testing.assert_allclose(
                histograms[name].axes[1][[0, -1]],
                [-1.0, 1.0],
            )
            values = histograms[name].values
            assert values.sum() == values[1:-1, 1:-1].sum() == 2


@pytest.mark.regression
def test_spherical_source_populates_both_angular_hemispheres(
    tmp_path, atris_command
):
    # MixMax u in (0, 1] makes GPS cos(theta) = 1 - 2u span [-1, 1),
    # exactly matching the histogram's inclusive-lower/exclusive-upper range.
    prepare_run(tmp_path)
    (tmp_path / "protons.mac").write_text(
        "/run/initialize\n"
        "/gps/particle proton\n"
        "/gps/ene/mono 10 MeV\n"
        "/gps/pos/type Surface\n"
        "/gps/pos/shape Sphere\n"
        "/gps/pos/centre 0 0 0 mm\n"
        "/gps/pos/radius 3 km\n"
        "/gps/ang/type cos\n"
        "/gps/ang/mintheta 0 deg\n"
        "/gps/ang/maxtheta 90 deg\n"
        "/random/setSeeds 123456 654321\n"
        "/run/beamOn 100\n"
    )

    result = run_atris(atris_command, tmp_path, "protons")

    assert result.returncode == 0, result.stdout + result.stderr
    with ResponseHistogramReader(tmp_path / "protons") as histograms:
        for name in ("h2.dir", "h2.pos"):
            values = histograms[name].values
            interior = values[1:-1, 1:-1]
            assert values.sum() == interior.sum() == 100
            assert interior[:, :30].sum() > 0
            assert interior[:, 30:].sum() > 0


@pytest.mark.regression
def test_unsupported_output_extension_fails_cleanly(tmp_path, atris_command):
    prepare_run(tmp_path)

    result = run_atris(atris_command, tmp_path, "protons.unsupported")

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "Cannot open analysis output 'protons.unsupported'" in output


@pytest.mark.regression
def test_mode_zero_writes_merged_root_interface_ntuple(tmp_path, atris_command):
    prepare_interface_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons.root",
        mode="0",
        threads="2",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    root_path = tmp_path / "protons.root"
    assert root_path.is_file()
    assert len(read_interface_records(root_path)) == 2
    assert has_ntuple(root_path, "interfaces")
    assert not has_ntuple(root_path, "steps")
    assert not list(tmp_path.glob("protons_t*.root"))


@pytest.mark.regression
def test_mode_one_writes_root_step_ntuple_with_track_genealogy(
    tmp_path, atris_command
):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons.root",
        mode="1",
        threads="2",
    )

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
def test_mode_one_contains_mode_zero_interface_records(tmp_path, atris_command):
    mode_zero = tmp_path / "mode-zero"
    mode_one = tmp_path / "mode-one"
    mode_zero.mkdir()
    mode_one.mkdir()
    prepare_interface_run(mode_zero)
    prepare_interface_run(mode_one)

    zero_result = run_atris(atris_command, mode_zero, "protons.root", mode="0")
    one_result = run_atris(atris_command, mode_one, "protons.root", mode="1")

    assert zero_result.returncode == 0, zero_result.stdout + zero_result.stderr
    assert one_result.returncode == 0, one_result.stdout + one_result.stderr
    np.testing.assert_array_equal(
        read_interface_records(mode_zero / "protons.root"),
        read_interface_records(mode_one / "protons.root"),
    )


@pytest.mark.regression
def test_seeded_prefix_uses_shared_chunk_inputs_and_seeded_output_prefix(
    tmp_path, atris_command
):
    prepare_run(tmp_path, chunked=True)
    simulation = "chunks/protons_123456_654321"

    result = run_atris(atris_command, tmp_path, simulation)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: using random seeds 123456 and 654321" in result.stdout
    assert "### AtRIS: executing macro protons.chunk.mac" in result.stdout

    prefix = "protons_123456_654321"
    written_suffixes = {
        path.name[len(prefix):]
        for path in (tmp_path / "chunks").glob(prefix + "_*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES
    assert histogram_entries(tmp_path / "chunks" / f"{prefix}_h1_h1.1.csv") == 1
    annotations = histogram_annotations(
        tmp_path / "chunks" / f"{prefix}_h1_h1.1.csv"
    )
    assert annotations["atris.random_seed_pairs"] == "123456:654321"
    assert not (tmp_path / "protons_h1_h1.1.csv").exists()


@pytest.mark.regression
def test_seeded_mode_one_writes_root_file_inside_chunks(tmp_path, atris_command):
    prepare_run(tmp_path, chunked=True)
    simulation = "chunks/protons_123456_654321"

    result = run_atris(
        atris_command,
        tmp_path,
        simulation + ".root",
        mode="1",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    root_path = tmp_path / (simulation + ".root")
    assert root_path.is_file()
    assert len(read_ntuple(root_path, "steps", STEP_FIELDS)) == 1
    assert not list((tmp_path / "chunks").glob("*.csv"))
    with uproot.open(root_path) as root_file:
        assert "h1.1" in root_file


@pytest.mark.regression
@pytest.mark.parametrize("chunks", [1, 2])
def test_csv_and_root_response_histograms_gather_equivalently(
    tmp_path, atris_command, chunks
):
    outputs = {}
    entries = [("protons", "123456", "654321"), ("protons", "223456", "754321")][:chunks]
    for mode, directory_name in (("-1", "csv"), ("0", "root")):
        run_directory = tmp_path / directory_name
        run_directory.mkdir()
        prepare_run(run_directory, chunked=True)
        shutil.copyfile(FIXTURE / "interface.gdml", run_directory / "protons.gdml")
        shutil.copyfile(FIXTURE / "interface.mac", run_directory / "protons.chunk.mac")
        shutil.copyfile(
            FIXTURE / "simulation.psf",
            run_directory / "simulation.psf",
        )
        shutil.copyfile(
            FIXTURE / "phantoms.txt",
            run_directory / "phantoms.txt",
        )

        for entry in entries:
            simulation = "chunks/" + "_".join(entry)
            result = run_atris(
                atris_command, run_directory,
                simulation + (".root" if mode == "0" else ""), mode=mode,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            (run_directory / (simulation + ".COMPLETE")).touch()
        gather_simulation(run_directory, entries, "protons")

        if mode == "0":
            with uproot.open(run_directory / "protons.root") as root_file:
                metadata = root_file["metadata"]
                assert metadata.num_entries == chunks
                assert metadata["random_seed_1"].array(
                    library="np"
                ).tolist() == [int(entry[1]) for entry in entries]
                assert metadata["random_seed_2"].array(
                    library="np"
                ).tolist() == [int(entry[2]) for entry in entries]

        with ResponseHistogramReader(run_directory / "protons") as histograms:
            outputs[mode] = {
                name: histograms[name]
                for name in histograms.names()
            }

    assert outputs["-1"].keys() == outputs["0"].keys()
    assert outputs["-1"]["h2.rates0.primary"].sumw2.sum() > 0
    for name in outputs["-1"]:
        csv_histogram = outputs["-1"][name]
        root_histogram = outputs["0"][name]
        for csv_axis, root_axis in zip(csv_histogram.axes, root_histogram.axes):
            np.testing.assert_allclose(csv_axis, root_axis, rtol=1e-6)
        np.testing.assert_allclose(csv_histogram.values, root_histogram.values, rtol=5e-6)
        if csv_histogram.sumw2 is not None and root_histogram.sumw2 is not None:
            np.testing.assert_allclose(csv_histogram.sumw2, root_histogram.sumw2, rtol=5e-6)


@pytest.mark.regression
def test_version_form_reports_version_without_simulation_inputs(tmp_path, atris_command):
    result = invoke_atris(atris_command, tmp_path, "--version")

    assert result.returncode == 0
    assert re.fullmatch(r"AtRIS \S+\n", result.stdout)
    assert result.stderr == ""


@pytest.mark.regression
@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param((), id="no-arguments"),
        pytest.param(("FTFP_BERT_HP",), id="too-few-arguments"),
        pytest.param(
            ("FTFP_BERT_HP", "protons", "-1", "1", "extra"),
            id="too-many-arguments",
        ),
    ],
)
def test_wrong_argument_count_prints_usage_and_currently_returns_success(
    tmp_path, atris_command, arguments
):
    result = invoke_atris(atris_command, tmp_path, *arguments)

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "<physics-list> <simulation-name> <mode> <phantom-count>" in result.stdout


@pytest.mark.regression
@pytest.mark.parametrize(
    ("mode", "phantom_count"),
    [
        pytest.param("not-an-integer", "1", id="nonnumeric-mode"),
        pytest.param("-1", "not-an-integer", id="nonnumeric-phantom-count"),
    ],
)
def test_nonnumeric_integer_arguments_exit_nonzero(
    tmp_path, atris_command, mode, phantom_count
):
    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        mode=mode,
        phantom_count=phantom_count,
    )

    assert result.returncode != 0
    assert not list(tmp_path.glob("*.csv"))


@pytest.mark.regression
def test_unsupported_physics_list_exits_nonzero(tmp_path, atris_command):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        physics="NOT_A_GEANT4_PHYSICS_LIST",
    )

    assert result.returncode != 0
    assert "NOT_A_GEANT4_PHYSICS_LIST is not valid" in result.stdout
    assert "FTFP_BERT_HP" in result.stdout
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
    tmp_path, atris_command, macro_contents
):
    prepare_run(tmp_path)
    macro = tmp_path / "protons.mac"
    if macro_contents is None:
        macro.unlink()
    else:
        macro.write_text(macro_contents)

    result = run_atris(atris_command, tmp_path, "protons")

    assert result.returncode != 0
    assert "### AtRIS: macro execution failed with Geant4 status" in result.stderr
    assert "### AtRIS: the simulation has completed" not in result.stdout


@pytest.mark.regression
def test_missing_geometry_exits_nonzero(tmp_path, atris_command):
    prepare_run(tmp_path)
    (tmp_path / "protons.gdml").unlink()

    result = run_atris(atris_command, tmp_path, "protons")

    assert result.returncode != 0
    assert "### AtRIS: the simulation has completed" not in result.stdout


@pytest.mark.regression
def test_missing_energy_bins_currently_runs_with_zero_edges(tmp_path, atris_command):
    prepare_run(tmp_path)
    (tmp_path / "protons.bins").unlink()

    result = run_atris(atris_command, tmp_path, "protons")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: read 0 binedges." in result.stdout
    assert "### AtRIS: the simulation has completed" in result.stdout
    assert {path.name for path in tmp_path.glob("protons_*.csv")} == {
        "protons_h2_h2.dir.csv",
        "protons_h2_h2.pos.csv",
    }


@pytest.mark.regression
def test_zero_phantom_count_runs_without_phantom_histograms(tmp_path, atris_command):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        phantom_count="0",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    written_suffixes = {
        path.name[len("protons"):]
        for path in tmp_path.glob("protons_*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS


@pytest.mark.regression
@pytest.mark.parametrize(
    "mismatched_file",
    ["radiation_phantom1.txt", "counting_phantom1.txt"],
)
def test_mismatched_phantom_pdg_headers_exit_nonzero(
    tmp_path, atris_command, mismatched_file
):
    prepare_run(tmp_path)
    shutil.copyfile(
        tmp_path / "radiation_phantom0.txt",
        tmp_path / "radiation_phantom1.txt",
    )
    shutil.copyfile(
        tmp_path / "counting_phantom0.txt",
        tmp_path / "counting_phantom1.txt",
    )

    path = tmp_path / mismatched_file
    lines = path.read_text().splitlines()
    lines[0] = " ".join(lines[0].split()[:-1])
    lines = lines[:-1]
    path.write_text("\n".join(lines) + "\n")

    result = run_atris(atris_command, tmp_path, "protons", phantom_count="2")

    assert result.returncode != 0
    assert "### AtRIS: PDG header mismatch:" in result.stderr
    assert mismatched_file in result.stderr
    assert "radiation_phantom0.txt" in result.stderr
    assert not list(tmp_path.glob("protons_*.csv"))


@pytest.mark.regression
@pytest.mark.parametrize("mode", ["-2", "2", "999"])
def test_undocumented_integer_modes_currently_follow_csv_path(
    tmp_path, atris_command, mode
):
    prepare_run(tmp_path)

    result = run_atris(atris_command, tmp_path, "protons", mode=mode)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "protons_h1_h1.1.csv").is_file()
    assert not (tmp_path / "protons.root").exists()


@pytest.mark.regression
def test_negative_phantom_count_currently_behaves_as_zero(tmp_path, atris_command):
    prepare_run(tmp_path)

    result = run_atris(
        atris_command,
        tmp_path,
        "protons",
        phantom_count="-1",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "### AtRIS: proceeding to load -1 phantom(s)." in result.stdout
    written_suffixes = {
        path.name[len("protons"):]
        for path in tmp_path.glob("protons_*.csv")
    }
    assert written_suffixes == EXPECTED_HISTOGRAM_SUFFIXES_WITHOUT_PHANTOMS
