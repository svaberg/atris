"""Prepare independently seeded AtRIS chunks from ordinary macros."""

import argparse
from collections import Counter
import logging
import os
from pathlib import Path
import random
import stat
import tempfile

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)


SPECIES = ("protons", "alphas")
logger = logging.getLogger(__name__)


def macro_lines_and_events(source):
    """Return macro lines, the beam command index, and its event count."""
    lines = source.read_text().splitlines(keepends=True)
    beam_lines = [
        index
        for index, line in enumerate(lines)
        if line.lstrip().startswith("/run/beamOn ")
    ]
    if len(beam_lines) != 1:
        raise ValueError(
            "%s must contain exactly one /run/beamOn command" % source
        )

    beam_index = beam_lines[0]
    fields = lines[beam_index].split()
    if len(fields) != 2:
        raise ValueError("Invalid /run/beamOn command in %s" % source)
    try:
        total_events = int(fields[1])
    except ValueError as error:
        raise ValueError("Invalid /run/beamOn command in %s" % source) from error
    if total_events < 1:
        raise ValueError(
            "/run/beamOn must request at least one event in %s" % source
        )

    return lines, beam_index, total_events


def chunk_macro(source, chunks):
    lines, beam_index, total_events = macro_lines_and_events(source)

    events_per_chunk = (total_events + chunks - 1) // chunks
    newline = "\n" if lines[beam_index].endswith("\n") else ""
    stripped_line = lines[beam_index].lstrip()
    indentation_length = len(lines[beam_index]) - len(stripped_line)
    indentation = lines[beam_index][:indentation_length]
    lines[beam_index] = "%s/run/beamOn %i%s" % (
        indentation,
        events_per_chunk,
        newline,
    )
    output_lines = [
        index
        for index, line in enumerate(lines)
        if line.lstrip().startswith("/atris/outputFile ")
    ]
    seed_lines = [
        index
        for index, line in enumerate(lines)
        if line.lstrip().startswith("/atris/randomSeeds ")
    ]
    if len(output_lines) != 1:
        raise ValueError(
            "%s must contain exactly one /atris/outputFile command" % source
        )
    if len(seed_lines) != 1:
        raise ValueError(
            "%s must contain exactly one /atris/randomSeeds command" % source
        )
    lines[output_lines[0]] = "/atris/outputFile {ATRIS_OUTPUT_FILE}\n"
    lines[seed_lines[0]] = "/atris/randomSeeds {ATRIS_SEED_1} {ATRIS_SEED_2}\n"
    contents = "".join(lines)
    return contents, total_events, events_per_chunk


def chunk_plan(chunks, rng, used_pairs=()):
    """Return new plan lines whose seed pairs do not occur in used_pairs."""
    used_pairs = set(used_pairs)
    lines = []
    for species in SPECIES:
        for _ in range(chunks):
            while True:
                seeds = (rng.randint(31, 999999), rng.randint(31, 999999))
                if seeds not in used_pairs:
                    break
            used_pairs.add(seeds)
            lines.append("%s %06i %06i\n" % (species, seeds[0], seeds[1]))
    return lines


def existing_plan(plan_path):
    """Return validated plan entries, existing seed pairs, and original text."""
    original = plan_path.read_text()
    entries = []
    used_pairs = set()
    for line_number, line in enumerate(original.splitlines(), start=1):
        fields = line.split()
        if len(fields) != 3:
            raise ValueError("Invalid chunks.txt line %i" % line_number)
        species, seed1_text, seed2_text = fields
        if species not in SPECIES:
            raise ValueError(
                "Invalid particle species on chunks.txt line %i" % line_number
            )
        try:
            seeds = (int(seed1_text), int(seed2_text))
        except ValueError as error:
            raise ValueError(
                "Invalid random seeds on chunks.txt line %i" % line_number
            ) from error
        if not all(31 <= seed <= 999999 for seed in seeds):
            raise ValueError(
                "Random seeds out of range on chunks.txt line %i" % line_number
            )
        if seeds in used_pairs:
            raise ValueError(
                "Duplicate random seed pair on chunks.txt line %i" % line_number
            )
        used_pairs.add(seeds)
        entries.append((species, seed1_text, seed2_text))

    if not entries:
        raise ValueError("Chunk plan is empty: " + str(plan_path))
    counts = Counter(species for species, _, _ in entries)
    missing = [species for species in SPECIES if not counts[species]]
    if missing:
        raise ValueError("Chunk plan has no %s entries" % " or ".join(missing))
    return entries, used_pairs, original


def replace_plan(plan_path, original, new_lines):
    """Atomically replace a plan with its original text plus new lines."""
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=plan_path.parent,
            prefix=plan_path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_name = output.name
            output.write(original)
            if original and not original.endswith("\n"):
                output.write("\n")
            output.writelines(new_lines)
        os.chmod(temporary_name, stat.S_IMODE(plan_path.stat().st_mode))
        os.replace(temporary_name, plan_path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def scatter(run_directory, chunks, random_seed=None):
    if chunks < 1:
        raise ValueError("chunks must be at least 1")

    run_directory = Path(run_directory).expanduser().resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError("Run directory does not exist: " + str(run_directory))

    plan_path = run_directory / "chunks.txt"
    chunks_directory = run_directory / "chunks"
    if plan_path.exists():
        raise FileExistsError("Chunk plan already exists: " + str(plan_path))
    if chunks_directory.exists():
        if not chunks_directory.is_dir():
            raise FileExistsError(
                "Chunk output path is not a directory: " + str(chunks_directory)
            )
        if any(chunks_directory.iterdir()):
            raise FileExistsError(
                "Chunk output directory is not empty: " + str(chunks_directory)
            )

    chunk_macros = {}
    rounded_totals = []
    for species in SPECIES:
        source = run_directory / (species + ".mac")
        destination = run_directory / (species + ".chunk.mac")
        if not source.is_file():
            raise FileNotFoundError("Ordinary macro does not exist: " + str(source))
        if destination.exists():
            raise FileExistsError("Chunk macro already exists: " + str(destination))
        contents, total_events, events_per_chunk = chunk_macro(source, chunks)
        chunk_macros[destination] = contents
        actual_events = events_per_chunk * chunks
        if actual_events != total_events:
            rounded_totals.append(
                (species, total_events, actual_events, events_per_chunk)
            )

    rng = random.Random(random_seed)
    plan_lines = chunk_plan(chunks, rng)
    chunks_directory.mkdir(exist_ok=True)
    for destination, contents in chunk_macros.items():
        destination.write_text(contents)
    with plan_path.open("x") as plan:
        plan.writelines(plan_lines)
    logger.debug("Wrote %i entries to %s", len(plan_lines), plan_path)
    for species, requested, actual, per_chunk in rounded_totals:
        logger.warning(
            "Rounded %s from %i requested events to %i across %i chunks "
            "(%i events per chunk)",
            species,
            requested,
            actual,
            chunks,
            per_chunk,
        )

    return run_directory


def extend_plan(run_directory, chunks, random_seed=None):
    """Append independently seeded chunks using the existing chunk macros."""
    if chunks < 1:
        raise ValueError("chunks must be at least 1")

    run_directory = Path(run_directory).expanduser().resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError("Run directory does not exist: " + str(run_directory))

    plan_path = run_directory / "chunks.txt"
    chunks_directory = run_directory / "chunks"
    if not plan_path.is_file():
        raise FileNotFoundError("Chunk plan does not exist: " + str(plan_path))
    if not chunks_directory.is_dir():
        raise FileNotFoundError(
            "Chunk output directory does not exist: " + str(chunks_directory)
        )

    entries, used_pairs, original = existing_plan(plan_path)
    existing_counts = Counter(species for species, _, _ in entries)
    events_per_chunk = {}
    for species in SPECIES:
        macro = run_directory / (species + ".chunk.mac")
        if not macro.is_file():
            raise FileNotFoundError("Chunk macro does not exist: " + str(macro))
        _, _, events_per_chunk[species] = macro_lines_and_events(macro)

    new_lines = chunk_plan(chunks, random.Random(random_seed), used_pairs)
    replace_plan(plan_path, original, new_lines)
    logger.debug("Appended %i entries to %s", len(new_lines), plan_path)

    for species in SPECIES:
        old_count = existing_counts[species]
        new_count = old_count + chunks
        per_chunk = events_per_chunk[species]
        logger.info(
            "Extended %s from %i to %i chunks: added %i events; "
            "cumulative plan %i events (%i per chunk)",
            species,
            old_count,
            new_count,
            chunks * per_chunk,
            new_count * per_chunk,
            per_chunk,
        )

    return run_directory


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Split the proton and alpha event totals in ordinary AtRIS macros "
            "into independently seeded, restartable chunks."
        ),
        epilog=(
            "The initial operation reads protons.mac and alphas.mac, leaves "
            "them unchanged, and writes chunks.txt, protons.chunk.mac, "
            "alphas.chunk.mac, and an empty chunks directory. Each species is "
            "split separately; --chunks N therefore creates 2N plan entries. "
            "If an event total is not divisible by N, each chunk receives the "
            "rounded-up count and the resulting small increase is reported. "
            "--extend adds new events using the established per-chunk size; it "
            "does not repartition existing work. This command does not run or "
            "gather any chunks."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        default=".",
        metavar="RUN_DIRECTORY",
        help="Prepared run directory (default: current directory).",
    )
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument(
        "--chunks",
        type=int,
        metavar="COUNT",
        help=(
            "Create a new plan with COUNT proton chunks and COUNT alpha "
            "chunks."
        ),
    )
    operation.add_argument(
        "--extend",
        type=int,
        metavar="COUNT",
        help=(
            "Append COUNT new chunks for each species to an existing plan, "
            "increasing the total simulated events."
        ),
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        metavar="SEED",
        help=(
            "Seed used to generate reproducible, unique Geant4 seed pairs "
            "for the plan (default: random)."
        ),
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    if args.chunks is not None:
        run_directory = scatter(args.run_directory, args.chunks, args.random_seed)
        logger.info(
            "Created %i proton chunks and %i alpha chunks (%i total) in %s",
            args.chunks,
            args.chunks,
            args.chunks * 2,
            run_directory,
        )
    else:
        run_directory = extend_plan(
            args.run_directory,
            args.extend,
            args.random_seed,
        )
        logger.info(
            "Added %i proton chunks and %i alpha chunks (%i total) to %s",
            args.extend,
            args.extend,
            args.extend * 2,
            run_directory,
        )


if __name__ == "__main__":
    main()
