import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import uproot

from atris_tools import postprocess
from atris_tools.response_histograms import (
    PRIMARY_HISTOGRAM,
    TOTAL_DEPOSITION_HISTOGRAM,
    ResponseHistogramReader,
    csv_histogram_axes,
    read_csv_histogram,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "minimal"


def write_root_response(path, include_total_deposition=True):
    energy_edges = np.array([1.0, 10.0, 100.0])
    detector_edges = np.array([-0.5, 0.5, 1.5, 2.5, 3.5])
    angular_edges = np.array([0.0, 0.5, 1.0])
    angular = np.arange(1.0, 5.0).reshape(2, 2)
    response = np.arange(1.0, 9.0).reshape(2, 4)
    with uproot.recreate(path) as root_file:
        root_file["h1.1"] = (np.array([4.0, 4.0]), energy_edges)
        root_file["h2.dir"] = (angular, angular_edges, angular_edges)
        root_file["h2.pos"] = (angular, angular_edges, angular_edges)
        root_file["h2.ion"] = (response, energy_edges, detector_edges)
        if include_total_deposition:
            root_file[TOTAL_DEPOSITION_HISTOGRAM] = (
                2 * response,
                energy_edges,
                detector_edges,
            )


def test_csv_histogram_axes_reads_edge_and_fixed_axes(tmp_path):
    histogram = tmp_path / "histogram.csv"
    histogram.write_text(
        "#axis edges 1 10 100\n"
        "#axis fixed 2 0 1\n"
        "entries,Sw\n"
    )

    axes = csv_histogram_axes(histogram)

    np.testing.assert_allclose(axes[0], [1, 10, 100])
    np.testing.assert_allclose(axes[1], [0, 0.5, 1])


def test_read_csv_histogram_accepts_variable_length_annotations(tmp_path):
    histogram = tmp_path / "histogram.csv"
    histogram.write_text(
        "#class tools::histo::h1d\n"
        "#annotation atris.quantity primary energy\n"
        "#annotation atris.random_seed_pairs 123456:654321\n"
        "entries,Sw\n"
        "2,3.5\n"
    )

    _, _, data = read_csv_histogram(histogram)
    np.testing.assert_allclose(data, [[2, 3.5]])


def test_input_output_warnings_report_mismatched_run_files(tmp_path, monkeypatch):
    (tmp_path / "protons.bins").write_text("1\n20\n100\n")
    (tmp_path / "protons.mac").write_text(
        "/gps/hist/point 1 0\n"
        "/gps/hist/point 20 1\n"
        "/gps/hist/point 100 1\n"
        "/run/beamOn 10\n"
    )
    (tmp_path / "protons_h1_h1.1.csv").write_text(
        "#class tools::histo::h1d\n"
        "#title kinetic energy\n"
        "#dimension 1\n"
        "#axis edges 1 10 100\n"
        "#annotation test\n"
        "#bin_number 4\n"
        "entries,Sw\n"
        "0,0\n4,0\n4,0\n0,0\n"
    )
    (tmp_path / "simulation.psf").write_text(
        "0 1 0 1 0 1 0 1 1 1 1 0 0 0 0 0\n"
        "1 2 0 1 0 1 1 1 1 1 1 0 0 0 0 0\n"
    )
    (tmp_path / "protons_h2_h2.ion.csv").write_text(
        "#axis edges 1 10 100\n"
        "#axis edges -0.5 0.5 1.5 2.5\n"
        "entries,Sw\n"
    )
    (tmp_path / "phantoms.txt").write_text("test  1.0  2.0\n")
    monkeypatch.chdir(tmp_path)

    warnings = postprocess.input_output_warnings("protons")

    assert warnings == [
        "protons: protons.bins does not match the energy edges recorded in "
        "protons_h1_h1.1.csv",
        "protons: protons.mac requests 10 events, but "
        "protons_h1_h1.1.csv records 8",
        "protons: simulation.psf defines 2 detector layers, but "
        "protons_h2_h2.ion.csv records 3",
        "protons: phantoms.txt selects test, but raw output contains no phantoms",
    ]


def test_input_output_warnings_accept_matching_energy_and_event_inputs(
    tmp_path, monkeypatch
):
    (tmp_path / "protons.bins").write_text("1\n10\n100\n")
    (tmp_path / "protons.mac").write_text(
        "/gps/hist/point 1 0\n"
        "/gps/hist/point 10 1\n"
        "/gps/hist/point 100 1\n"
        "/run/beamOn 8\n"
    )
    (tmp_path / "protons_h1_h1.1.csv").write_text(
        "#class tools::histo::h1d\n"
        "#title kinetic energy\n"
        "#dimension 1\n"
        "#axis edges 1 10 100\n"
        "#annotation test\n"
        "#bin_number 4\n"
        "entries,Sw\n"
        "0,0\n4,0\n4,0\n0,0\n"
    )
    monkeypatch.chdir(tmp_path)

    assert postprocess.input_output_warnings("protons") == []


def test_input_output_warnings_report_angular_flow_entries(tmp_path, monkeypatch):
    (tmp_path / "protons_h1_h1.1.csv").write_text(
        "#axis edges 1 10 100\n"
        "entries,Sw\n"
        "0,0\n4,0\n4,0\n0,0\n"
    )
    angular_rows = np.zeros((4, 4))
    angular_rows[0, 1] = 3
    angular_rows[2, 2] = 5
    table = "".join("0,%g\n" % value for value in angular_rows.T.ravel())
    for name in ("dir", "pos"):
        (tmp_path / ("protons_h2_h2.%s.csv" % name)).write_text(
            "#axis fixed 2 0 6.283185307179586\n"
            "#axis fixed 2 -1 1\n"
            "entries,Sw\n"
            + table
        )
    monkeypatch.chdir(tmp_path)

    warnings = postprocess.input_output_warnings("protons")

    assert warnings == [
        "protons: protons_h2_h2.dir.csv contains 3 entries in the "
        "source-direction histogram's underflow or overflow bins",
        "protons: protons_h2_h2.pos.csv contains 3 entries in the "
        "source-position histogram's underflow or overflow bins",
    ]


def test_process_psf_and_phantoms_return_numpy_data(tmp_path, monkeypatch):
    geometry, detector_count = postprocess.process_psf(FIXTURE / "simulation.psf")

    assert detector_count == 2
    assert geometry.keys() == {"sdid", "volume/cm3", "inn_surface/cm2"}
    np.testing.assert_array_equal(geometry["sdid"], [0, 1])
    assert all(isinstance(values, np.ndarray) for values in geometry.values())

    shutil.copy2(FIXTURE / "phantoms.txt", tmp_path)
    monkeypatch.chdir(tmp_path)
    phantoms = postprocess.process_phantoms(["icru_zero"])
    np.testing.assert_allclose(phantoms, [[14094.7550, 1413.72]])


def test_process_phantoms_accepts_run_without_phantoms(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    phantoms = postprocess.process_phantoms([])

    assert phantoms.shape == (0, 2)


def test_process_phantoms_uses_stems_independently_of_row_order(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "phantoms.txt").write_text(
        "second  30.5 40.5\n"
        "first   10.5 20.5\n"
    )
    monkeypatch.chdir(tmp_path)

    phantoms = postprocess.process_phantoms(["first", "second"])

    np.testing.assert_allclose(phantoms, [[10.5, 20.5], [30.5, 40.5]])


def test_main_skips_missing_species(tmp_path, monkeypatch, caplog):
    (tmp_path / "protons_h1_h1.1.csv").write_text("present\n")
    processed = []
    monkeypatch.setattr(postprocess, "process_run", processed.append)
    monkeypatch.setattr(sys, "argv", ["atris-postprocess", str(tmp_path)])

    with caplog.at_level(logging.INFO, logger="atris_tools.postprocess"):
        postprocess.main()

    assert processed == ["protons"]
    assert "Skipping alphas: output not found" in caplog.messages


def test_main_accepts_directory_without_simulation_output(
    tmp_path, monkeypatch, caplog
):
    processed = []
    monkeypatch.setattr(postprocess, "process_run", processed.append)
    monkeypatch.setattr(sys, "argv", ["atris-postprocess", str(tmp_path)])

    with caplog.at_level(logging.INFO, logger="atris_tools.postprocess"):
        postprocess.main()

    assert processed == []
    assert "No requested simulation output found" in caplog.text


def test_main_rejects_species_argument(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["atris-postprocess", str(tmp_path), "protons"],
    )

    with pytest.raises(SystemExit):
        postprocess.main()


def test_postprocess_reads_root_response_histograms(tmp_path, monkeypatch):
    write_root_response(tmp_path / "protons.root")
    (tmp_path / "simulation.psf").write_text(
        "0 1 0 1 0 1 0 1 1 1 1 0 0 0 0 0\n"
        "1 2 0 1 0 1 1 1 1 1 1 0 0 0 0 0\n"
        "2 3 0 1 0 1 2 1 1 1 1 0 0 0 0 0\n"
        "3 4 0 1 0 1 3 1 1 1 1 0 0 0 0 0\n"
    )
    monkeypatch.chdir(tmp_path)

    with ResponseHistogramReader("protons") as histograms:
        assert histograms.phantom_stems() == set()
        np.testing.assert_array_equal(
            histograms.axes(PRIMARY_HISTOGRAM)[0],
            [1.0, 10.0, 100.0],
        )
        np.testing.assert_array_equal(
            histograms.values(PRIMARY_HISTOGRAM)[1:-1], [4.0, 4.0]
        )
        np.testing.assert_array_equal(
            histograms.values("h2.ion")[1:-1, 1:-1],
            np.arange(1.0, 9.0).reshape(2, 4),
        )
        np.testing.assert_array_equal(
            histograms.values(TOTAL_DEPOSITION_HISTOGRAM)[1:-1, 1:-1],
            2 * np.arange(1.0, 9.0).reshape(2, 4),
        )

    postprocess.process_run("protons")

    assert (tmp_path / "protons.ioni").is_file()
    assert (tmp_path / "protons.edep").is_file()
    ionization = np.loadtxt(tmp_path / "protons.ioni")[:, 2:]
    total_deposition = np.loadtxt(tmp_path / "protons.edep")[:, 2:]
    np.testing.assert_allclose(total_deposition, 2 * ionization, rtol=1e-5)


def test_postprocess_accepts_output_without_total_deposition(
    tmp_path, monkeypatch
):
    write_root_response(
        tmp_path / "protons.root",
        include_total_deposition=False,
    )
    (tmp_path / "simulation.psf").write_text(
        "0 1 0 1 0 1 0 1 1 1 1 0 0 0 0 0\n"
        "1 2 0 1 0 1 1 1 1 1 1 0 0 0 0 0\n"
        "2 3 0 1 0 1 2 1 1 1 1 0 0 0 0 0\n"
        "3 4 0 1 0 1 3 1 1 1 1 0 0 0 0 0\n"
    )
    monkeypatch.chdir(tmp_path)

    postprocess.process_run("protons")

    assert (tmp_path / "protons.ioni").is_file()
    assert not (tmp_path / "protons.edep").exists()


def test_postprocess_rejects_ambiguous_response_formats(tmp_path, monkeypatch):
    write_root_response(tmp_path / "protons.root")
    (tmp_path / "protons_h1_h1.1.csv").write_text("present\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Both CSV and ROOT"):
        ResponseHistogramReader("protons")
