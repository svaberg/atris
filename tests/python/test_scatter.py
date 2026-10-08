import logging
import random
import re

import pytest

from atris_tools.scatter import chunk_plan, extend_plan, scatter

ORDINARY_MACRO = """/atris/geometryFile {species}.gdml
/atris/energyBinsFile {species}.bins
# Use this filename stem for all simulation output.
/atris/outputStem {species}
# Set the two random seeds before initialization.
/atris/randomSeeds 123456 654321
/atris/initialize
/gps/particle {particle}
# Process 7 events with the configuration above.
/run/beamOn 7
"""


def write_ordinary_macros(run_directory):
    contents = {}
    for species, particle in (("protons", "proton"), ("alphas", "alpha")):
        text = ORDINARY_MACRO.format(species=species, particle=particle)
        (run_directory / f"{species}.mac").write_text(text)
        contents[species] = text
    return contents


def test_chunk_plan_is_reproducible_unique_and_six_digit():
    first = chunk_plan(4, random.Random(20260827))
    second = chunk_plan(4, random.Random(20260827))

    assert first == second
    assert len(first) == 8
    assert [line.split()[0] for line in first] == ["protons"] * 4 + ["alphas"] * 4
    assert all(
        re.fullmatch(r"(?:protons|alphas) \d{6} \d{6}\n", line) for line in first
    )

    pairs = [tuple(line.split()[1:]) for line in first]
    assert len(set(pairs)) == len(pairs)


def test_chunk_plan_skips_seed_pairs_already_in_an_existing_plan():
    original = chunk_plan(2, random.Random(17))
    used_pairs = {tuple(int(seed) for seed in line.split()[1:]) for line in original}

    extension = chunk_plan(1, random.Random(17), used_pairs)
    extension_pairs = {
        tuple(int(seed) for seed in line.split()[1:]) for line in extension
    }

    assert len(extension) == 2
    assert used_pairs.isdisjoint(extension_pairs)


def test_scatter_preserves_ordinary_macros_and_rounds_chunk_event_count(
    tmp_path, caplog
):
    originals = write_ordinary_macros(tmp_path)
    (tmp_path / "chunks").mkdir()

    with caplog.at_level(logging.WARNING, logger="atris_tools.scatter"):
        result = scatter(tmp_path, chunks=2, random_seed=17)

    assert result == tmp_path.resolve()
    assert (tmp_path / "chunks").is_dir()
    assert list((tmp_path / "chunks").iterdir()) == []
    assert len((tmp_path / "chunks.txt").read_text().splitlines()) == 4

    for species in ("protons", "alphas"):
        assert (tmp_path / f"{species}.mac").read_text() == originals[species]
        chunk = (tmp_path / f"{species}.chunk.mac").read_text()
        assert "/atris/outputStem {ATRIS_OUTPUT_STEM}" in chunk
        assert "/atris/randomSeeds {ATRIS_SEED_1} {ATRIS_SEED_2}" in chunk
        assert "/atris/outputStem %s" % species not in chunk
        assert "/atris/randomSeeds 123456 654321" not in chunk
        assert "/run/beamOn 4" in chunk
        assert (
            "# atris-run supplies a separate output stem for each chunk.\n"
            "/atris/outputStem {ATRIS_OUTPUT_STEM}\n" in chunk
        )
        assert (
            "# atris-run supplies two positive random seeds for each chunk.\n"
            "/atris/randomSeeds {ATRIS_SEED_1} {ATRIS_SEED_2}\n" in chunk
        )
        assert "# Process 4 events in each chunk.\n/run/beamOn 4\n" in chunk

    assert caplog.messages == [
        "Rounded protons from 7 requested events to 8 across 2 chunks "
        "(4 events per chunk)",
        "Rounded alphas from 7 requested events to 8 across 2 chunks "
        "(4 events per chunk)",
    ]


def test_scatter_logs_nothing_when_event_count_divides_evenly(tmp_path, caplog):
    write_ordinary_macros(tmp_path)
    for macro in tmp_path.glob("*.mac"):
        macro.write_text(macro.read_text().replace("/run/beamOn 7", "/run/beamOn 8"))

    scatter(tmp_path, chunks=2, random_seed=17)

    assert caplog.messages == []
    for species in ("protons", "alphas"):
        chunk = (tmp_path / f"{species}.chunk.mac").read_text()
        assert "/run/beamOn 4" in chunk


def test_scatter_rejects_missing_event_count_before_writing(tmp_path):
    write_ordinary_macros(tmp_path)
    (tmp_path / "alphas.mac").write_text("/atris/initialize\n")

    with pytest.raises(ValueError, match="exactly one /run/beamOn"):
        scatter(tmp_path, chunks=2, random_seed=17)

    assert not (tmp_path / "protons.chunk.mac").exists()
    assert not (tmp_path / "alphas.chunk.mac").exists()
    assert not (tmp_path / "chunks.txt").exists()
    assert not (tmp_path / "chunks").exists()


def test_scatter_refuses_all_destinations_before_writing(tmp_path):
    write_ordinary_macros(tmp_path)
    existing = tmp_path / "alphas.chunk.mac"
    existing.write_text("keep me\n")

    with pytest.raises(FileExistsError, match="alphas.chunk.mac"):
        scatter(tmp_path, chunks=1, random_seed=3)

    assert existing.read_text() == "keep me\n"
    assert not (tmp_path / "protons.chunk.mac").exists()
    assert not (tmp_path / "chunks.txt").exists()
    assert not (tmp_path / "chunks").exists()


def test_scatter_rejects_nonempty_chunks_directory(tmp_path):
    write_ordinary_macros(tmp_path)
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    (chunks / "partial.csv").write_text("partial\n")

    with pytest.raises(FileExistsError, match="not empty"):
        scatter(tmp_path, chunks=1)

    assert not (tmp_path / "protons.chunk.mac").exists()
    assert not (tmp_path / "alphas.chunk.mac").exists()
    assert not (tmp_path / "chunks.txt").exists()


def test_scatter_rejects_zero_chunks(tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        scatter(tmp_path, chunks=0)


def test_extend_plan_preserves_existing_work_and_adds_unique_chunks(tmp_path, caplog):
    write_ordinary_macros(tmp_path)
    scatter(tmp_path, chunks=2, random_seed=17)
    caplog.clear()
    original_plan = (tmp_path / "chunks.txt").read_text()
    original_macros = {
        species: (tmp_path / f"{species}.chunk.mac").read_text()
        for species in ("protons", "alphas")
    }
    marker = tmp_path / "chunks" / "existing.COMPLETE"
    marker.write_text("keep\n")

    with caplog.at_level(logging.INFO, logger="atris_tools.scatter"):
        result = extend_plan(tmp_path, chunks=1, random_seed=17)

    assert result == tmp_path.resolve()
    extended_lines = (tmp_path / "chunks.txt").read_text().splitlines()
    assert extended_lines[:4] == original_plan.splitlines()
    assert [line.split()[0] for line in extended_lines] == [
        "protons",
        "protons",
        "alphas",
        "alphas",
        "protons",
        "alphas",
    ]
    seed_pairs = [tuple(line.split()[1:]) for line in extended_lines]
    assert len(set(seed_pairs)) == 6
    assert marker.read_text() == "keep\n"
    for species in ("protons", "alphas"):
        assert (tmp_path / f"{species}.chunk.mac").read_text() == original_macros[
            species
        ]
    assert caplog.messages == [
        "Extended protons from 2 to 3 chunks: added 4 events; "
        "cumulative plan 12 events (4 per chunk)",
        "Extended alphas from 2 to 3 chunks: added 4 events; "
        "cumulative plan 12 events (4 per chunk)",
    ]


def test_extend_plan_validates_every_input_before_replacing_plan(tmp_path):
    write_ordinary_macros(tmp_path)
    scatter(tmp_path, chunks=2, random_seed=17)
    plan = tmp_path / "chunks.txt"
    original_plan = plan.read_text()
    (tmp_path / "alphas.chunk.mac").unlink()

    with pytest.raises(FileNotFoundError, match="alphas.chunk.mac"):
        extend_plan(tmp_path, chunks=1)

    assert plan.read_text() == original_plan


def test_extend_plan_rejects_duplicate_existing_seed_pairs(tmp_path):
    write_ordinary_macros(tmp_path)
    scatter(tmp_path, chunks=1, random_seed=17)
    plan = tmp_path / "chunks.txt"
    lines = plan.read_text().splitlines()
    fields = lines[0].split()
    lines[1] = "alphas %s %s" % (fields[1], fields[2])
    plan.write_text("\n".join(lines) + "\n")
    invalid_plan = plan.read_text()

    with pytest.raises(ValueError, match="Duplicate random seed pair"):
        extend_plan(tmp_path, chunks=1)

    assert plan.read_text() == invalid_plan


def test_extend_plan_rejects_zero_chunks(tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        extend_plan(tmp_path, chunks=0)


def test_scatter_and_extend_electrons_without_proton_or_alpha_macros(tmp_path):
    original = ORDINARY_MACRO.format(species="electrons", particle="e-")
    macro = tmp_path / "electrons.mac"
    macro.write_text(original)

    scatter(tmp_path, chunks=2, random_seed=42, simulations=("electrons",))
    first_plan = (tmp_path / "chunks.txt").read_text()
    chunk_macro = (tmp_path / "electrons.chunk.mac").read_text()
    assert len(first_plan.splitlines()) == 2
    assert all(line.startswith("electrons ") for line in first_plan.splitlines())
    assert "/gps/particle e-" in chunk_macro
    assert "/run/beamOn 4" in chunk_macro

    extend_plan(tmp_path, chunks=1, random_seed=42)
    extended = (tmp_path / "chunks.txt").read_text()
    assert extended.startswith(first_plan)
    assert len(extended.splitlines()) == 3
    assert all(line.startswith("electrons ") for line in extended.splitlines())
    assert len({tuple(line.split()[1:]) for line in extended.splitlines()}) == 3
    assert macro.read_text() == original
    assert (tmp_path / "electrons.chunk.mac").read_text() == chunk_macro
