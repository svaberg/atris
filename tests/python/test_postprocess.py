import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import uproot

from atris_tools import postprocess
from atris_tools.histogram import read_root_histograms, write_root_histograms
from atris_tools.histogram import (
    PRIMARY_HISTOGRAM,
    TOTAL_DEPOSITION_HISTOGRAM,
    ResponseHistogramReader,
    Histogram,
    csv_histogram_axes,
    read_csv_histogram,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "minimal"


@pytest.mark.parametrize("squared_weights", [False, True])
def test_histogram_keeps_available_csv_uncertainties(tmp_path, squared_weights):
    (tmp_path / "protons_h1_h1.1.csv").write_text(
        "#axis edges 1 10\nentries,Sw\n0,0\n2,2\n0,0\n")
    path = tmp_path / "protons_h2_h2.ion.csv"
    header = "#axis edges 1 10\n#axis edges 0 1\n#annotation atris.unit MeV\n"
    path.write_text(header + ("entries,Sw,Sw2\n" if squared_weights else "entries,Sw\n")
                    + ("2,3,5\n" if squared_weights else "2,3\n") * 9)
    with ResponseHistogramReader(tmp_path / "protons") as histograms:
        histogram = histograms["h2.ion"]
        assert isinstance(histogram, Histogram)
        np.testing.assert_array_equal(histogram.values, np.full((3, 3), 3))
        assert histogram.annotations == tuple(header.splitlines())
        summary = str(histogram)
        assert "Value shape: (3, 3)" in summary
        assert "Axis 0: 1 bin from 1 to 10" in summary
        assert "Values include underflow and overflow bins" in summary
        assert "Squared-weight sums: " + ("available" if squared_weights else "unavailable") in summary
        assert repr(histogram).startswith("Histogram(values=array(")
        if squared_weights:
            np.testing.assert_array_equal(histogram.sumw2, np.full((3, 3), 5))
        else:
            assert histogram.sumw2 is None


def test_histogram_rejects_inconsistent_arrays_and_incompatible_addition():
    axes = [np.array([1, 10])]
    with pytest.raises(ValueError, match="values do not match"):
        Histogram(np.ones(2), axes)
    with pytest.raises(ValueError, match="squared-weight sums"):
        Histogram(np.ones(3), axes, sumw2=np.ones(2))
    first = Histogram(np.ones(3), axes)
    other = Histogram(np.ones(3), [np.array([1, 20])])
    with pytest.raises(ValueError, match="axes differ"):
        first.add(other, "test")
    np.testing.assert_array_equal(first.values, np.ones(3))


@pytest.mark.parametrize("counts", [0, 1, 2, 4])
def test_primary_mean_variance_includes_zero_score_primaries(tmp_path, counts):
    (tmp_path / "protons_h1_h1.1.csv").write_text(
        f"#axis edges 1 10\nentries,Sw\n0,0\n{counts},{counts}\n0,0\n")
    # Primary totals [3, 1, 0, 0] give S=4, Q=10; a four-primary mean
    # has variance 0.5. Companion entries alone must not be used as N.
    path = tmp_path / "protons_h2_h2.ion.primary.csv"
    path.write_text("#axis edges 1 10\n#axis edges 0 1\nentries,Sw,Sw2\n"
                    + "0,0,0\n" * 4 + "2,4,10\n" + "0,0,0\n" * 4)
    with ResponseHistogramReader(tmp_path / "protons") as reader:
        variance = reader.mean_variance("h2.ion")
        assert np.isnan(variance[[0, 2]]).all()
        if counts < 2:
            assert np.isnan(variance).all()
        else:
            assert variance[1, 1] == pytest.approx(1 if counts == 2 else 0.5)
            np.testing.assert_array_equal(variance[1, [0, 2]], 0)
        with pytest.raises(ValueError, match="unavailable"):
            reader.mean_variance("h2.edep")


def test_primary_mean_variance_rejects_missing_or_inconsistent_moments(tmp_path):
    (tmp_path / "protons_h1_h1.1.csv").write_text(
        "#axis edges 1 10\nentries,Sw\n0,0\n2,2\n0,0\n")
    path = tmp_path / "protons_h2_h2.ion.primary.csv"
    with ResponseHistogramReader(tmp_path / "protons") as reader:
        for columns, row, message in (("entries,Sw", "2,4", "unavailable"),
                                      ("entries,Sw,Sw2", "2,4,1", "Inconsistent")):
            path.write_text("#axis edges 1 10\n#axis edges 0 1\n"
                            + columns + "\n" + (row + "\n") * 9)
            with pytest.raises(ValueError, match=message):
                reader.mean_variance("h2.ion")


def test_primary_mean_variance_warns_when_csv_rounding_limits_subtraction(tmp_path):
    (tmp_path / "protons_h1_h1.1.csv").write_text(
        "#axis edges 1 10\nentries,Sw\n0,0\n2,2\n0,0\n")
    (tmp_path / "protons_h2_h2.ion.primary.csv").write_text(
        "#axis edges 1 10\n#axis edges 0 1\nentries,Sw,Sw2\n"
        + "0,0,0\n" * 4 + "2,2.46914,3.04831\n" + "0,0,0\n" * 4)
    with ResponseHistogramReader(tmp_path / "protons") as reader:
        with pytest.warns(RuntimeWarning, match="CSV rounding"):
            variance = reader.mean_variance("h2.ion")
        assert variance[1, 1] == 0


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


def test_histogram_root_roundtrip_preserves_labels_and_bin_statistics(tmp_path):
    source = tmp_path / "source.root"
    write_root_response(source)
    original, metadata = read_root_histograms(source)
    assert original["h2.ion"].sumw2 is None
    original["h2.ion"].sumw2 = np.full_like(original["h2.ion"].values, 7)
    original["h2.ion"].title = "Ionizing energy"
    original["h2.ion"].axis_titles = ("Energy (MeV)", "Detector ID")
    destination = tmp_path / "roundtrip.root"
    assert write_root_histograms(destination, original, metadata) == destination
    restored, _ = read_root_histograms(destination)
    for name, first in original.items():
        second = restored[name]
        assert second.title == first.title
        assert second.axis_titles == first.axis_titles
        if name == "h2.ion":
            assert "Histogram: Ionizing energy" in str(second)
            assert "Energy (MeV): 2 bins from 1 to 100" in str(second)
        assert second.statistics == first.statistics
        np.testing.assert_array_equal(second.values, first.values)
        if first.sumw2 is None:
            assert second.sumw2 is None
        else:
            np.testing.assert_array_equal(second.sumw2, first.sumw2)
        for first_axis, second_axis in zip(first.axes, second.axes):
            np.testing.assert_array_equal(second_axis, first_axis)


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

    data = read_csv_histogram(histogram)
    np.testing.assert_allclose(data.bin_statistics, [[2, 3.5]])
    assert data.axes == []
    assert "Bin edges unavailable" in str(data)
    assert "flow bins" not in str(data)


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
        + "0,0\n" * 20
    )
    (tmp_path / "phantoms.txt").write_text("0  test  1.0  2.0\n")
    monkeypatch.chdir(tmp_path)

    warnings = postprocess.input_output_warnings("protons")

    assert warnings == [
        "protons: protons.bins does not match the energy edges recorded in "
        "protons_h1_h1.1.csv",
        "protons: protons.mac requests 10 events, but "
        "protons_h1_h1.1.csv records 8",
        "protons: simulation.psf defines 2 detector layers, but "
        "protons_h2_h2.ion.csv records 3",
        "protons: phantoms.txt defines 1 phantoms, but raw output contains 0",
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
    geometry, detector_count = postprocess.detector_geometry(FIXTURE / "simulation.psf")

    assert detector_count == 2
    assert geometry.keys() == {"sdid", "volume/cm3", "inn_surface/cm2"}
    np.testing.assert_array_equal(geometry["sdid"], [0, 1])
    assert all(isinstance(values, np.ndarray) for values in geometry.values())

    shutil.copy2(FIXTURE / "phantoms.txt", tmp_path)
    monkeypatch.chdir(tmp_path)
    phantoms = postprocess.process_phantoms(1)
    np.testing.assert_allclose(phantoms, [[14094.7550, 1413.72]])


def test_process_phantoms_accepts_run_without_phantoms(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    phantoms = postprocess.process_phantoms(0)

    assert phantoms.shape == (0, 2)


def test_process_phantoms_uses_ids_independently_of_row_order(tmp_path, monkeypatch):
    (tmp_path / "phantoms.txt").write_text(
        "1  second  30.5 40.5\n"
        "0  first   10.5 20.5\n"
    )
    monkeypatch.chdir(tmp_path)

    phantoms = postprocess.process_phantoms(2)

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
        assert histograms.phantom_count() == 0
        np.testing.assert_array_equal(
            histograms[PRIMARY_HISTOGRAM].axes[0],
            [1.0, 10.0, 100.0],
        )
        np.testing.assert_array_equal(
            histograms[PRIMARY_HISTOGRAM].values[1:-1], [4.0, 4.0]
        )
        np.testing.assert_array_equal(
            histograms["h2.ion"].values[1:-1, 1:-1],
            np.arange(1.0, 9.0).reshape(2, 4),
        )
        np.testing.assert_array_equal(
            histograms[TOTAL_DEPOSITION_HISTOGRAM].values[1:-1, 1:-1],
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
