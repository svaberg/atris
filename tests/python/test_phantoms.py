import logging
import os
from pathlib import Path

import pytest

from atris_tools.phantoms import read_phantoms, stage_phantoms


def make_archive(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    for name in ("first", "second"):
        (archive / (name + "_response.txt")).write_text(name + " radiation\n")
        (archive / (name + "_counting.txt")).write_text(name + " counting\n")
    return archive


def write_phantoms(
    run_directory,
    rows=(
        "first    1.5  2.5\n"
        "second  30.5 40.5\n"
    ),
):
    contents = "# Phantom  mass [g]  area [cm2]\n" + rows
    (run_directory / "phantoms.txt").write_text(contents)
    return contents


def test_phantom_ids_follow_row_order(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    metadata = write_phantoms(
        run_directory,
        "second  30.5 40.5\n"
        "first   10.5 20.5\n",
    )

    count = stage_phantoms(run_directory, archive)
    phantoms = read_phantoms(run_directory)

    assert count == 2
    assert [(phantom["id"], phantom["stem"]) for phantom in phantoms] == [
        (0, "second"),
        (1, "first"),
    ]
    radiation = run_directory / "first_response.txt"
    counting = run_directory / "second_counting.txt"
    assert radiation.is_symlink()
    assert counting.is_symlink()
    assert not os.path.isabs(os.readlink(radiation))
    assert radiation.read_text() == "first radiation\n"
    assert counting.read_text() == "second counting\n"
    assert (run_directory / "phantoms.txt").read_text() == metadata


def test_stage_phantoms_can_copy_files(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(
        run_directory,
        "first  1.5 2.5\n",
    )

    stage_phantoms(run_directory, archive, copy=True)

    local_radiation = run_directory / "first_response.txt"
    local_counting = run_directory / "first_counting.txt"
    assert local_radiation.is_file()
    assert local_counting.is_file()
    assert not local_radiation.is_symlink()
    assert not local_counting.is_symlink()
    assert local_radiation.read_text() == "first radiation\n"
    assert local_counting.read_text() == "first counting\n"


def test_stage_phantoms_copy_replaces_matching_links(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(
        run_directory,
        "first  1.5 2.5\n",
    )
    stage_phantoms(run_directory, archive)

    stage_phantoms(run_directory, archive, copy=True)
    stage_phantoms(run_directory, archive, copy=True)

    local_radiation = run_directory / "first_response.txt"
    local_counting = run_directory / "first_counting.txt"
    assert local_radiation.is_file()
    assert local_counting.is_file()
    assert not local_radiation.is_symlink()
    assert not local_counting.is_symlink()
    assert local_radiation.read_text() == "first radiation\n"
    assert local_counting.read_text() == "first counting\n"


def test_stage_phantoms_updates_links_after_selection_changes(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "first  1.5 2.5\n")
    stage_phantoms(run_directory, archive)

    write_phantoms(run_directory, "second  3.5 4.5\n")
    count = stage_phantoms(run_directory, archive)

    assert count == 1
    radiation = run_directory / "second_response.txt"
    counting = run_directory / "second_counting.txt"
    assert radiation.is_symlink()
    assert counting.is_symlink()
    assert radiation.resolve() == archive / "second_response.txt"
    assert counting.resolve() == archive / "second_counting.txt"
    assert (run_directory / "first_response.txt").is_symlink()
    assert (run_directory / "first_counting.txt").is_symlink()


def test_stage_phantoms_copy_keeps_old_files_and_updates_links(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "first  1.5 2.5\n")
    stage_phantoms(run_directory, archive, copy=True)

    write_phantoms(run_directory, "second  3.5 4.5\n")
    count = stage_phantoms(run_directory, archive, copy=True)

    assert count == 1
    assert (run_directory / "first_response.txt").is_file()
    assert (run_directory / "first_counting.txt").is_file()
    assert (run_directory / "second_response.txt").is_file()
    assert (run_directory / "second_counting.txt").is_file()


def test_stage_phantoms_leaves_descriptive_links_for_removed_rows(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory)
    stage_phantoms(run_directory, archive)

    write_phantoms(run_directory, "first  1.5 2.5\n")
    count = stage_phantoms(run_directory, archive)

    assert count == 1
    assert (run_directory / "first_response.txt").is_symlink()
    assert (run_directory / "first_counting.txt").is_symlink()
    assert (run_directory / "second_response.txt").is_symlink()
    assert (run_directory / "second_counting.txt").is_symlink()


def test_stage_phantoms_keeps_old_links_when_replacement_is_missing(
    tmp_path, caplog
):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "first  1.5 2.5\n")
    stage_phantoms(run_directory, archive)

    write_phantoms(run_directory, "missing  3.5 4.5\n")
    count = stage_phantoms(run_directory, archive)

    assert count == 0
    assert (run_directory / "first_response.txt").is_symlink()
    assert (run_directory / "first_counting.txt").is_symlink()
    assert "missing_response.txt" in caplog.messages[-1]


def test_stage_phantoms_does_not_remove_regular_files_for_removed_rows(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "first  1.5 2.5\n")
    stale_file = run_directory / "radiation_phantom1.txt"
    stale_file.write_text("keep me\n")

    stage_phantoms(run_directory, archive)

    assert stale_file.read_text() == "keep me\n"


def test_stage_phantoms_accepts_custom_files_in_run_directory(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    (run_directory / "custom_response.txt").write_text("custom radiation\n")
    (run_directory / "custom_counting.txt").write_text("custom counting\n")
    write_phantoms(
        run_directory,
        "custom  7.5 8.5\n",
    )

    stage_phantoms(run_directory)

    assert (run_directory / "custom_response.txt").read_text() == (
        "custom radiation\n"
    )
    assert (run_directory / "custom_counting.txt").read_text() == (
        "custom counting\n"
    )


def test_stage_phantoms_stages_absolute_stem_under_local_names(tmp_path):
    source = tmp_path / "elsewhere" / "custom"
    source.parent.mkdir()
    Path(str(source) + "_response.txt").write_text("custom radiation\n")
    Path(str(source) + "_counting.txt").write_text("custom counting\n")
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "%s  7.5 8.5\n" % source)

    stage_phantoms(run_directory)

    assert (run_directory / "custom_response.txt").is_symlink()
    assert (run_directory / "custom_counting.txt").is_symlink()


def test_stage_phantoms_accepts_run_without_phantoms(tmp_path):
    run_directory = tmp_path / "run"
    run_directory.mkdir()

    assert stage_phantoms(run_directory) == 0
    assert list(run_directory.iterdir()) == []


def test_stage_phantoms_keeps_existing_regular_files(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory)
    existing = run_directory / "second_counting.txt"
    existing.write_text("keep me\n")

    count = stage_phantoms(run_directory, archive)

    assert count == 2
    assert existing.read_text() == "keep me\n"
    assert (run_directory / "first_response.txt").is_symlink()
    assert (run_directory / "first_counting.txt").is_symlink()
    assert (run_directory / "second_response.txt").is_symlink()


def test_stage_phantoms_logs_missing_source_and_keeps_other_rows(tmp_path, caplog):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    metadata = write_phantoms(run_directory)
    (archive / "second_counting.txt").unlink()

    count = stage_phantoms(run_directory, archive)

    assert count == 1
    assert (run_directory / "first_response.txt").is_symlink()
    assert (run_directory / "first_counting.txt").is_symlink()
    assert not (run_directory / "second_response.txt").exists()
    assert not (run_directory / "second_counting.txt").exists()
    assert (run_directory / "phantoms.txt").read_text() == metadata
    assert "second_counting.txt" in caplog.messages[-1]


def test_stage_phantoms_can_create_dummy_counting_response(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    archive = make_archive(tmp_path)
    (archive / "first_response.txt").write_text("22 2212\n")
    (archive / "first_counting.txt").unlink()
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "first  1.5 2.5\n")

    count = stage_phantoms(
        run_directory,
        archive,
        accept_missing_counting=True,
    )
    count_again = stage_phantoms(
        run_directory,
        archive,
        accept_missing_counting=True,
    )

    assert count == 1
    assert count_again == 1
    dummy = run_directory / "first_dummy_counting.txt"
    lines = dummy.read_text().splitlines()
    assert lines[0] == "22 2212"
    assert len(lines) == 3
    for line in lines[1:]:
        values = line.split()
        assert len(values) == 650
        assert set(values) == {"1.000000e+00"}
    assert "dummy counting response with values of one" in caplog.messages[-1]


def test_stage_phantoms_prefers_real_counting_response(tmp_path):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "first  1.5 2.5\n")

    count = stage_phantoms(
        run_directory,
        archive,
        accept_missing_counting=True,
    )

    assert count == 1
    assert not (run_directory / "first_dummy_counting.txt").exists()
    counting = run_directory / "first_counting.txt"
    assert counting.resolve() == archive / "first_counting.txt"


def test_stage_phantoms_does_not_overwrite_existing_dummy_file(tmp_path, caplog):
    archive = make_archive(tmp_path)
    (archive / "first_response.txt").write_text("22 2212\n")
    (archive / "first_counting.txt").unlink()
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, "first  1.5 2.5\n")
    dummy = run_directory / "first_dummy_counting.txt"
    dummy.write_text("keep me\n")

    count = stage_phantoms(
        run_directory,
        archive,
        accept_missing_counting=True,
    )

    assert count == 0
    assert dummy.read_text() == "keep me\n"
    assert not (run_directory / "first_response.txt").exists()
    assert "Refusing to overwrite" in caplog.messages[-1]


def test_stage_phantoms_continues_after_missing_file(tmp_path, caplog):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(
        run_directory,
        "missing  1.5 2.5\nsecond  3.5 4.5\n",
    )

    count = stage_phantoms(run_directory, archive)

    assert count == 1
    assert not (run_directory / "missing_response.txt").exists()
    assert not (run_directory / "missing_counting.txt").exists()
    assert (run_directory / "second_response.txt").is_symlink()
    assert (run_directory / "second_counting.txt").is_symlink()
    assert "missing_response.txt" in caplog.messages[-1]


@pytest.mark.parametrize(
    "rows",
    (
        "first  1.5\n",
        "first  not-a-mass  2.5\n",
    ),
)
def test_stage_phantoms_rejects_invalid_rows(tmp_path, rows):
    archive = make_archive(tmp_path)
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    write_phantoms(run_directory, rows)

    with pytest.raises(ValueError, match="Expected|Invalid"):
        stage_phantoms(run_directory, archive)

    assert list(run_directory.iterdir()) == [run_directory / "phantoms.txt"]
