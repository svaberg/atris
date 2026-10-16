import logging
import os
from pathlib import Path

import numpy as np
import pytest
import uproot

from atris_tools.convergence import (
    change_reference_count,
    fractional_change,
    ionization_response,
    log_ionization_change,
    write_convergence,
)
from atris_tools.chunks import (
    chunk_progress,
    format_duration,
    log_chunk_progress,
    read_chunk_plan,
)
from atris_tools.gather import (
    combine_ionization_histograms,
    gather_histogram,
    gather_incremental_histogram,
    gather_simulation,
)
from atris_tools.histogram import read_csv_histogram


COLUMNS = "entries,Sw,Sw2,Sxw0,Sx2w0"


def write_histogram(
    path,
    rows,
    *,
    plane_sum=1.0,
    title="kinetic energy",
    seed_pairs=None,
    annotation=None,
    axes=(),
    columns=COLUMNS,
):
    lines = [
        "#class tools::histo::h1d",
        f"#title {title}",
        "#dimension %i" % (len(axes) or 1),
        f"#planes_Sxyw {plane_sum}",
    ]
    lines.extend(axes)
    if seed_pairs is not None:
        lines.append("#annotation atris.random_seed_pairs " + seed_pairs)
    if annotation is not None:
        lines.append("#annotation " + annotation)
    lines.append(columns)
    lines.extend(",".join(str(value) for value in row) for row in rows)
    Path(path).write_text("\n".join(lines) + "\n")


def write_root_histograms(path, primary, direction, ionization=None):
    energy_edges = np.array([1.0, 10.0, 100.0])
    phi_edges = np.array([0.0, 1.0, 2.0])
    cosine_edges = np.array([0.0, 0.5, 1.0])
    with uproot.recreate(path) as root_file:
        root_file["h1.1"] = (np.asarray(primary, dtype=float), energy_edges)
        root_file["h2.dir"] = (
            np.asarray(direction, dtype=float),
            phi_edges,
            cosine_edges,
        )
        if ionization is not None:
            root_file["h2.ion"] = (
                np.asarray(ionization, dtype=float),
                energy_edges,
                np.array([-0.5, 0.5, 1.5, 2.5]),
            )
        root_file["interfaces"] = {"event_id": np.array([1], dtype=np.int32)}


def test_read_chunk_plan_reports_malformed_line_number(tmp_path):
    (tmp_path / "chunks.txt").write_text(
        "protons 123456 654321\n"
        "alphas only-two-fields\n"
    )

    with pytest.raises(ValueError, match=r"line 2$"):
        read_chunk_plan(tmp_path)


def test_chunk_progress_estimates_from_completion_marker_times(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "%06i" % seed, "%06i" % (seed + 1))
        for seed in range(100, 105)
    ]
    for entry, timestamp in zip(entries[:3], (100, 110, 120)):
        simulation, seed1, seed2 = entry
        marker = chunks / ("%s_%s_%s.COMPLETE" % (simulation, seed1, seed2))
        marker.touch()
        os.utime(marker, (timestamp, timestamp))

    assert chunk_progress(tmp_path, entries, ("protons",)) == (3, 5, 10, 20)


def test_chunk_progress_filters_species_and_logs_estimate(tmp_path, caplog):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
        ("protons", "555555", "666666"),
        ("alphas", "777777", "888888"),
    ]
    for index, (_, seed1, seed2) in enumerate(entries[:2]):
        marker = chunks / ("protons_%s_%s.COMPLETE" % (seed1, seed2))
        marker.touch()
        os.utime(marker, (100 + index * 65, 100 + index * 65))

    with caplog.at_level(logging.INFO, logger="atris_tools"):
        log_chunk_progress(tmp_path, entries, ("protons",))

    assert caplog.messages == [
        "Chunk progress: 2/3 complete; average completion interval 1m 5s; "
        "estimated time remaining 1m 5s."
    ]


def test_chunk_progress_reports_complete_and_formats_long_durations(
    tmp_path, caplog
):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [("alphas", "111111", "222222")]
    (chunks / "alphas_111111_222222.COMPLETE").touch()

    with caplog.at_level(logging.INFO, logger="atris_tools"):
        log_chunk_progress(tmp_path, entries, ("alphas",))

    assert caplog.messages == ["Chunk progress: 1/1 complete."]
    assert format_duration(2 * 24 * 60 * 60 + 3 * 60 * 60) == "2d 3h"


def test_chunk_progress_does_not_treat_zero_second_estimate_as_complete(
    tmp_path, caplog
):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
        ("protons", "555555", "666666"),
    ]
    for _, seed1, seed2 in entries[:2]:
        marker = chunks / ("protons_%s_%s.COMPLETE" % (seed1, seed2))
        marker.touch()
        os.utime(marker, (100, 100))

    with caplog.at_level(logging.INFO, logger="atris_tools"):
        log_chunk_progress(tmp_path, entries, ("protons",))

    assert caplog.messages == [
        "Chunk progress: 2/3 complete; average completion interval 0s; "
        "estimated time remaining 0s."
    ]


def test_change_reference_uses_final_ten_percent_from_two_chunks():
    assert change_reference_count(1) is None
    assert change_reference_count(2) == 1
    assert change_reference_count(10) == 9
    assert change_reference_count(11) == 9
    assert change_reference_count(26) == 23
    assert change_reference_count(32) == 28


def test_fractional_change_treats_unsampled_cells_as_zero():
    previous = np.array([1.0, np.nan, 3.0])
    current = np.array([1.0, 2.0, 1.0])

    assert fractional_change(previous, current) == pytest.approx(4.0 / 8.0)


def test_ionization_response_matches_postprocess_scaling():
    primary_energy = np.array([0.0, 2.0, 4.0, 0.0])
    ionization = np.arange(20).reshape(5, 4).T
    geometry = {"volume/cm3": np.array([2.0, 4.0, 8.0])}

    response = ionization_response(primary_energy, ionization, geometry)

    np.testing.assert_allclose(response, [[9.0 / 8.0, 10.0 / 16.0]])


def test_convergence_has_one_row_per_chunk_from_two_onward(
    tmp_path, monkeypatch
):
    geometry = {"volume/cm3": np.ones(3)}
    monkeypatch.setattr(
        "atris_tools.convergence.detector_geometry", lambda path: (geometry, 3)
    )
    primary = np.array([0.0, 1.0, 1.0, 0.0])
    primary_snapshots = {count: count * primary for count in (1, 2, 3)}
    ionization_paths = []
    for count, value in enumerate((1.0, 3.0, 2.0), start=1):
        path = tmp_path / ("ionization-%i.csv" % count)
        write_histogram(
            path,
            [[0, value, 0, 0, 0]] * 20,
            axes=("#axis edges 1 10 100", "#axis edges 0 1 2 3"),
        )
        ionization_paths.append(path)

    _, rows = combine_ionization_histograms(
        tmp_path,
        ionization_paths,
        primary_snapshots,
    )

    assert [row[0] for row in rows] == [2, 3]
    np.testing.assert_allclose(
        rows[0],
        [2, 4, 1, 50.0, 100.0 / 3, 100.0 / 3, 100.0 / 3, 50.0, 50.0],
    )
    np.testing.assert_allclose(
        rows[1],
        [3, 6, 1, 100.0 / 3, 0.0, 0.0, 0.0, 100 / np.sqrt(12), 100 / np.sqrt(12)],
    )

    output = tmp_path / "protons.convergence.csv"
    write_convergence(output, rows)
    lines = output.read_text().splitlines()
    assert lines[0] == (
        "completed_chunks,primary_events,comparison_chunks,"
        "comparison_percent,ionization_change_percent,"
        "cell_change_p50_percent,cell_change_p90_percent,"
        "cell_relative_se_p50_percent,cell_relative_se_p90_percent"
    )
    assert len(lines) == 3


def test_ionization_change_reports_actual_comparison_fraction(caplog):
    row = (21, 6300, 3, 100.0 * 3 / 21, 1.802)

    with caplog.at_level(logging.INFO, logger="atris_tools"):
        log_ionization_change("alphas", row)

    assert caplog.messages == [
        "Alpha ionization change after final 3 of 21 completed chunks "
        "(14.3%): 1.80%"
    ]


def test_gather_histogram_sums_all_columns_and_plane_values(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    destination = tmp_path / "total.csv"
    write_histogram(first, [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]], plane_sum=2.5)
    write_histogram(second, [[10, 20, 30, 40, 50], [60, 70, 80, 90, 100]], plane_sum=4.0)

    total = gather_histogram([first, second], destination)

    np.testing.assert_array_equal(
        total.bin_statistics,
        np.array([[11, 22, 33, 44, 55], [66, 77, 88, 99, 110]], dtype=float),
    )
    written = read_csv_histogram(destination)
    assert "#planes_Sxyw 6.5" in written.annotations
    assert written.columns == tuple(COLUMNS.split(","))
    np.testing.assert_array_equal(written.bin_statistics, total.bin_statistics)

    first_result = destination.read_bytes()
    gather_histogram([first, second], destination)
    assert destination.read_bytes() == first_result


def test_gather_histogram_combines_seed_provenance(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    destination = tmp_path / "total.csv"
    write_histogram(first, [[1, 2, 3, 4, 5]], seed_pairs="123456:654321")
    write_histogram(second, [[1, 2, 3, 4, 5]], seed_pairs="111111:222222")

    gather_histogram([first, second], destination)

    header = read_csv_histogram(destination).annotations
    assert "#annotation atris.gathered_chunks 2" in header
    assert (
        "#annotation atris.random_seed_pairs "
        "123456:654321,111111:222222"
    ) in header
    assert "#annotation atris.random_seed_pairs_complete true" in header


def test_gather_rectangular_histogram_keeps_every_moment_and_bin_order(tmp_path):
    columns = "entries,Sw,Sw2,Sxw0,Sx2w0,Sxw1,Sx2w1,Sxyw"
    rows = np.arange(1, 161, dtype=float).reshape(20, 8)
    axes = ("#axis fixed 2 0 2", "#axis edges 0 1 2 3")
    first, second, destination = (tmp_path / name for name in ("first.csv", "second.csv", "sum.csv"))
    write_histogram(first, rows, axes=axes, columns=columns)
    write_histogram(second, 2 * rows, axes=axes, columns=columns)
    original = first.read_bytes()
    total = gather_histogram([first, second], destination)
    expected = (3 * rows).reshape(5, 4, 8).swapaxes(0, 1)
    written = read_csv_histogram(destination)
    np.testing.assert_array_equal(total.bin_statistics, expected)
    np.testing.assert_array_equal(written.bin_statistics, expected)
    np.testing.assert_array_equal(total.entries, expected[..., 0])
    np.testing.assert_array_equal(total.values, expected[..., 1])
    np.testing.assert_array_equal(total.sumw2, expected[..., 2])
    assert written.columns == tuple(columns.split(","))
    assert first.read_bytes() == original


def test_gather_histogram_records_different_atris_annotations(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    write_histogram(first, [[1, 2, 3, 4, 5]], annotation="atris.quantity ionization")
    write_histogram(second, [[1, 2, 3, 4, 5]], annotation="atris.quantity dose")

    destination = tmp_path / "total.csv"
    gather_histogram([first, second], destination)

    header = read_csv_histogram(destination).annotations
    assert "#annotation atris.quantity ionization | dose" in header


def test_incremental_gather_reads_only_new_chunks(tmp_path, monkeypatch):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    destination = tmp_path / "total.csv"
    state = tmp_path / "protons.gathered-chunks.txt"
    write_histogram(
        first, [[1, 2, 3, 4, 5]], seed_pairs="111111:222222"
    )
    write_histogram(
        second, [[10, 20, 30, 40, 50]], seed_pairs="333333:444444"
    )
    gather_histogram([first], destination)
    state.write_text("protons 111111 222222\n")

    reads = []
    original_read_histogram = read_csv_histogram

    def record_read(path):
        reads.append(Path(path))
        return original_read_histogram(path)

    monkeypatch.setattr("atris_tools.gather.read_csv_histogram", record_read)
    gather_incremental_histogram(
        [("protons", "111111", "222222")],
        [
            ("protons", "111111", "222222"),
            ("protons", "333333", "444444"),
        ],
        state.stat().st_mtime_ns,
        [first, second],
        destination,
    )

    assert reads == [destination, second]
    total = original_read_histogram(destination)
    header = total.annotations
    np.testing.assert_array_equal(total.bin_statistics, [[11, 22, 33, 44, 55]])
    assert "#annotation atris.gathered_chunks 2" in header
    assert (
        "#annotation atris.random_seed_pairs "
        "111111:222222,333333:444444"
    ) in header


def test_incremental_gather_rebuilds_after_prior_chunk_changes(
    tmp_path, monkeypatch
):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    destination = tmp_path / "total.csv"
    state = tmp_path / "protons.gathered-chunks.txt"
    write_histogram(first, [[1, 2, 3, 4, 5]])
    write_histogram(second, [[10, 20, 30, 40, 50]])
    gather_histogram([first], destination)
    state.write_text("protons 111111 222222\n")
    write_histogram(first, [[2, 4, 6, 8, 10]])

    reads = []
    original_read_histogram = read_csv_histogram

    def record_read(path):
        reads.append(Path(path))
        return original_read_histogram(path)

    monkeypatch.setattr("atris_tools.gather.read_csv_histogram", record_read)
    gather_incremental_histogram(
        [("protons", "111111", "222222")],
        [
            ("protons", "111111", "222222"),
            ("protons", "333333", "444444"),
        ],
        state.stat().st_mtime_ns,
        [first, second],
        destination,
    )

    assert reads == [first, second]
    total = original_read_histogram(destination)
    np.testing.assert_array_equal(total.bin_statistics, [[12, 24, 36, 48, 60]])


@pytest.mark.parametrize("difference", ["header", "shape", "columns"])
def test_gather_histogram_rejects_incompatible_input_without_replacing_destination(
    tmp_path, difference
):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    destination = tmp_path / "total.csv"
    write_histogram(first, [[1, 2, 3, 4, 5]])

    if difference == "header":
        write_histogram(second, [[1, 2, 3, 4, 5]], title="different")
    elif difference == "shape":
        write_histogram(second, [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]])
    else:
        write_histogram(second, [[1, 2, 3, 4, 5]])
        second.write_text(second.read_text().replace(COLUMNS, "entries,Sw,other,Sxw0,Sx2w0"))

    destination.write_text("existing canonical output\n")
    with pytest.raises(ValueError):
        gather_histogram([first, second], destination)

    assert destination.read_text() == "existing canonical output\n"


def test_gather_simulation_uses_only_completed_chunks(tmp_path, caplog):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
    ]
    complete_prefix = chunks / "protons_111111_222222"
    unfinished_prefix = chunks / "protons_333333_444444"
    complete_prefix.with_name(complete_prefix.name + ".COMPLETE").touch()
    write_histogram(
        complete_prefix.with_name(complete_prefix.name + "_h1_h1.1.csv"),
        [[0, 0, 0, 0, 0], [3, 30, 300, 300, 3000]],
    )
    write_histogram(
        unfinished_prefix.with_name(unfinished_prefix.name + "_h1_h1.1.csv"),
        [[99, 99, 99, 99, 99]],
    )

    with caplog.at_level(logging.INFO, logger="atris_tools"):
        assert gather_simulation(tmp_path, entries, "protons") == 1
    assert "Gathering protons from 1 completed chunk..." in caplog.messages

    histogram = read_csv_histogram(tmp_path / "protons_h1_h1.1.csv")
    np.testing.assert_array_equal(
        histogram.bin_statistics,
        np.array([[0, 0, 0, 0, 0], [3, 30, 300, 300, 3000]], dtype=float),
    )
    assert not (tmp_path / "alphas_h1_h1.1.csv").exists()


def test_gather_simulation_with_no_complete_chunks_writes_nothing(tmp_path):
    (tmp_path / "chunks").mkdir()

    assert gather_simulation(
        tmp_path, [("alphas", "123456", "654321")], "alphas"
    ) == 0
    assert list(tmp_path.glob("alphas_*.csv")) == []


def test_gather_simulation_combines_root_response_histograms_only(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
    ]
    first = chunks / "protons_111111_222222"
    second = chunks / "protons_333333_444444"
    write_root_histograms(
        Path(str(first) + ".root"),
        [2, 3],
        [[1, 2], [3, 4]],
    )
    write_root_histograms(
        Path(str(second) + ".root"),
        [5, 7],
        [[10, 20], [30, 40]],
    )
    Path(str(first) + ".COMPLETE").touch()
    Path(str(second) + ".COMPLETE").touch()

    assert gather_simulation(tmp_path, entries, "protons") == 2

    with uproot.open(tmp_path / "protons.root") as root_file:
        assert set(root_file.keys(cycle=False)) == {"h1.1", "h2.dir"}
        np.testing.assert_array_equal(root_file["h1.1"].values(), [7, 10])
        np.testing.assert_array_equal(
            root_file["h2.dir"].values(),
            [[11, 22], [33, 44]],
        )
        assert root_file["h1.1"].member("fEntries") == 17


def test_gather_simulation_rejects_mixed_response_formats(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
    ]
    first = chunks / "protons_111111_222222"
    second = chunks / "protons_333333_444444"
    write_root_histograms(
        Path(str(first) + ".root"),
        [2, 3],
        [[1, 2], [3, 4]],
    )
    write_histogram(
        Path(str(second) + "_h1_h1.1.csv"),
        [[0, 0, 0, 0, 0], [5, 5, 5, 5, 5]],
    )
    Path(str(first) + ".COMPLETE").touch()
    Path(str(second) + ".COMPLETE").touch()

    with pytest.raises(ValueError, match=r"mix (CSV and ROOT|ROOT and CSV)"):
        gather_simulation(tmp_path, entries, "protons")


@pytest.mark.parametrize("new_first", [False, True])
@pytest.mark.parametrize("output", ["csv", "root"])
def test_gather_rejects_missing_primary_moments_before_writing(tmp_path, new_first, output):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [("protons", "111111", "222222"), ("protons", "333333", "444444")]
    for index, entry in enumerate(entries):
        prefix = chunks / "_".join(entry)
        Path(str(prefix) + ".COMPLETE").touch()
        has_moments = (index == 0) == new_first
        if output == "csv":
            write_histogram(Path(str(prefix) + "_h1_h1.1.csv"), [[2, 2, 2, 0, 0]])
            if has_moments:
                write_histogram(Path(str(prefix) + "_h2_h2.ion.primary.csv"), [[2, 4, 10, 0, 0]])
        else:
            write_root_histograms(Path(str(prefix) + ".root"), [2, 2], [[0, 0], [0, 0]])
            if has_moments:
                with uproot.update(Path(str(prefix) + ".root")) as root:
                    root["h2.ion.primary"] = (np.ones((2, 2)), np.array([1, 10, 100]),
                                               np.array([0, 1, 2]))
    with pytest.raises((ValueError, FileNotFoundError), match="histogram"):
        gather_simulation(tmp_path, entries, "protons")
    assert not list(tmp_path.glob("protons*"))


def test_gather_root_histograms_writes_convergence(tmp_path, monkeypatch):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    entries = [
        ("protons", "111111", "222222"),
        ("protons", "333333", "444444"),
    ]
    geometry = {"volume/cm3": np.ones(3)}
    monkeypatch.setattr(
        "atris_tools.convergence.detector_geometry", lambda path: (geometry, 3)
    )
    for entry, value in zip(entries, (1.0, 3.0)):
        prefix = chunks / ("%s_%s_%s" % entry)
        write_root_histograms(
            Path(str(prefix) + ".root"),
            [2, 2],
            [[1, 2], [3, 4]],
            np.full((2, 3), value),
        )
        Path(str(prefix) + ".COMPLETE").touch()

    gather_simulation(tmp_path, entries, "protons")

    convergence = np.atleast_2d(
        np.loadtxt(
            tmp_path / "protons.convergence.csv",
            delimiter=",",
            skiprows=1,
        )
    )
    assert convergence.shape == (1, 9)
    assert convergence[0, 0] == 2
    with uproot.open(tmp_path / "protons.root") as root_file:
        np.testing.assert_array_equal(
            root_file["h2.ion"].values(),
            np.full((2, 3), 4.0),
        )
