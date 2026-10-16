"""Gather completed AtRIS repetitions into canonical histogram files."""

from pathlib import Path
import argparse
import logging

import numpy as np

from .chunks import chunk_name, complete_entries, log_chunk_progress, read_chunk_plan, read_plan
from .cli import HelpFormatter, add_logging_arguments, add_version_argument, configure_logging
from .convergence import ionization_convergence_observer, log_ionization_change, write_convergence
from .file_io import atomic_text_output
from .histogram import (
    ATRIS_ANNOTATION_PREFIX,
    IONIZATION_HISTOGRAM,
    PRIMARY_HISTOGRAM,
    read_csv_histogram,
    read_root_histograms,
    response_output_format,
    write_root_histograms,
)


SEED_PAIRS_PREFIX = "#annotation atris.random_seed_pairs "
GATHERED_CHUNKS_PREFIX = "#annotation atris.gathered_chunks "
SEED_PAIRS_COMPLETE_PREFIX = "#annotation atris.random_seed_pairs_complete "
logger = logging.getLogger(__name__)


def merge_provenance(headers):
    """Combine AtRIS annotations without making them gather constraints."""
    represented_chunks = 0
    seed_pairs = []
    has_provenance = False
    annotations = {}
    for header in headers:
        chunk_count = 1
        for line in header:
            if line.startswith(GATHERED_CHUNKS_PREFIX):
                chunk_count = int(line[len(GATHERED_CHUNKS_PREFIX):])
                has_provenance = True
            elif line.startswith(SEED_PAIRS_PREFIX):
                values = line[len(SEED_PAIRS_PREFIX):]
                if values and values != "runtime-default":
                    seed_pairs.extend(values.split(","))
                has_provenance = True
            elif line.startswith(SEED_PAIRS_COMPLETE_PREFIX):
                has_provenance = True
            elif line.startswith(ATRIS_ANNOTATION_PREFIX):
                fields = line.split(" ", 2)
                key = fields[1]
                value = fields[2] if len(fields) == 3 else ""
                values = annotations.setdefault(key, [])
                if value not in values:
                    values.append(value)
        represented_chunks += chunk_count

    output_header = [
        line for line in headers[0]
        if not line.startswith(ATRIS_ANNOTATION_PREFIX)
    ]
    merged_annotations = [
        "#annotation %s %s" % (key, " | ".join(values))
        for key, values in sorted(annotations.items())
    ]
    if has_provenance:
        merged_annotations.append(GATHERED_CHUNKS_PREFIX + str(represented_chunks))
        if seed_pairs:
            merged_annotations.append(SEED_PAIRS_PREFIX + ",".join(seed_pairs))
        merged_annotations.append(
            SEED_PAIRS_COMPLETE_PREFIX + str(len(seed_pairs) == represented_chunks).lower()
        )
    insertion = next(
        (
            index
            for index, line in enumerate(output_header)
            if line.startswith("#bin_number ")
        ),
        len(output_header),
    )
    output_header[insertion:insertion] = merged_annotations
    return output_header


def write_histogram(path, histogram):
    """Atomically write the CSV representation of a histogram."""
    with atomic_text_output(path) as output:
        histogram.write_csv(output)


def write_gathered_chunks(path, entries):
    """Write the gathered subset of chunks.txt atomically."""
    with atomic_text_output(path) as output:
        for entry in entries:
            output.write("%s %s %s\n" % entry)


def combine_csv_histograms(source_paths, snapshot_counts=(), observe=None):
    snapshot_counts = set(snapshot_counts)
    total = read_csv_histogram(source_paths[0])
    headers = [total.annotations]
    snapshots = {1: total.entries.copy()} if 1 in snapshot_counts else {}
    if observe is not None:
        observe(1, total, total)

    for source_number, source_path in enumerate(source_paths[1:], start=2):
        current = read_csv_histogram(source_path)
        headers.append(current.annotations)
        total.add(current, str(source_path))
        if source_number in snapshot_counts:
            snapshots[source_number] = total.entries.copy()
        if observe is not None:
            observe(source_number, current, total)

    total.annotations = tuple(merge_provenance(headers))
    return total, snapshots


def gather_histogram(source_paths, destination):
    total, _ = combine_csv_histograms(source_paths)
    write_histogram(destination, total)
    return total


def reusable_chunk_count(
    gathered_entries,
    current_entries,
    state_mtime,
    source_paths,
    destination,
):
    """Return the number of chunks already present in a valid aggregate."""
    gathered_count = len(gathered_entries)
    if (
        not gathered_count
        or current_entries[:gathered_count] != gathered_entries
        or not destination.is_file()
    ):
        return None

    output_mtime = destination.stat().st_mtime_ns
    if output_mtime > state_mtime:
        return None
    if any(
        path.stat().st_mtime_ns > output_mtime
        for path in source_paths[:gathered_count]
    ):
        return None
    return gathered_count


def gather_incremental_histogram(
    gathered_entries,
    current_entries,
    state_mtime,
    source_paths,
    destination,
):
    """Reuse a valid aggregate and add only newly completed chunks."""
    gathered_count = reusable_chunk_count(
        gathered_entries,
        current_entries,
        state_mtime,
        source_paths,
        destination,
    )
    if gathered_count is None:
        logger.debug("Rebuilding histogram %s", destination.name)
        gather_histogram(source_paths, destination)
    elif gathered_count < len(source_paths):
        logger.debug(
            "Adding %i new chunks to %s",
            len(source_paths) - gathered_count,
            destination.name,
        )
        gather_histogram(
            [destination] + source_paths[gathered_count:],
            destination,
        )
    else:
        logger.debug("Histogram %s is up to date", destination.name)


def combine_ionization_histograms(
    run_directory, source_paths, primary_snapshots
):
    """Combine ionization files and calculate convergence after every chunk."""
    observe, rows = ionization_convergence_observer(
        run_directory, len(source_paths), primary_snapshots
    )
    total, _ = combine_csv_histograms(
        source_paths, observe=observe
    )
    return total, rows


def gather_root_simulation(
    run_directory, current_entries, prefixes, simulation
):
    """Gather response histograms from ROOT chunks, leaving ntuples sharded."""
    source_paths = [Path(str(prefix) + ".root") for prefix in prefixes]
    primary_snapshots = {}
    convergence = []
    convergence_observer = None

    def observe(count, current, total):
        nonlocal convergence_observer, convergence
        primary_snapshots[count] = total[PRIMARY_HISTOGRAM].values.copy()
        if IONIZATION_HISTOGRAM not in total:
            return
        if convergence_observer is None:
            convergence_observer, convergence = ionization_convergence_observer(
                run_directory,
                len(source_paths),
                primary_snapshots,
            )
        convergence_observer(
            count,
            current[IONIZATION_HISTOGRAM],
            total[IONIZATION_HISTOGRAM],
        )

    histograms, metadata = combine_root_histograms(
        source_paths, observe=observe
    )
    primary = histograms[PRIMARY_HISTOGRAM]
    primary_events = primary.statistics["fEntries"]
    if not np.isclose(primary.values.sum(), primary_events):
        raise ValueError(
            "%s ROOT chunks contain weighted %s histograms; per-bin primary "
            "counts are unavailable" % (simulation, PRIMARY_HISTOGRAM)
        )

    write_root_histograms(
        run_directory / (simulation + ".root"),
        histograms,
        metadata,
    )
    logger.info(
        "Gathered %i completed %s runs containing %i primary events",
        len(prefixes),
        simulation,
        round(primary_events),
    )
    if convergence:
        write_convergence(
            run_directory / (simulation + ".convergence.csv"), convergence
        )
        log_ionization_change(simulation, convergence[-1])
    write_gathered_chunks(
        run_directory / (simulation + ".gathered-chunks.txt"),
        current_entries,
    )
    return len(prefixes)


def gather_simulation(run_directory, entries, simulation):
    current_entries = complete_entries(run_directory, entries, simulation)
    chunks_directory = run_directory / "chunks"
    prefixes = [
        chunks_directory / chunk_name(entry)
        for entry in current_entries
    ]
    if not prefixes:
        logger.info("No completed %s runs to gather", simulation)
        return 0
    logger.info(
        "Gathering %s from %i completed %s...",
        simulation,
        len(prefixes),
        "chunk" if len(prefixes) == 1 else "chunks",
    )

    first_prefix = prefixes[0]
    output_format = response_output_format(first_prefix)
    if output_format is None:
        raise FileNotFoundError(
            "Completed run has no response histograms: " + str(first_prefix)
        )
    for prefix in prefixes[1:]:
        current_format = response_output_format(prefix)
        if current_format != output_format:
            raise ValueError(
                "Completed chunks mix %s and %s response output"
                % (output_format.upper(), (current_format or "missing").upper())
            )
    if output_format == "root":
        return gather_root_simulation(
            run_directory,
            current_entries,
            prefixes,
            simulation,
        )

    histogram_paths = sorted(first_prefix.parent.glob(first_prefix.name + "_*.csv"))
    if not histogram_paths:
        raise FileNotFoundError("Completed run has no histogram files: " + str(first_prefix))

    paths_by_suffix = {}
    for first_path in histogram_paths:
        suffix = first_path.name[len(first_prefix.name):]
        source_paths = [prefix.parent / (prefix.name + suffix) for prefix in prefixes]
        for source_path in source_paths:
            if not source_path.is_file():
                raise FileNotFoundError("Missing histogram from completed run: " + str(source_path))
        paths_by_suffix[suffix] = source_paths
    for prefix in prefixes[1:]:
        suffixes = {path.name[len(prefix.name):]
                    for path in prefix.parent.glob(prefix.name + "_*.csv")}
        if suffixes != paths_by_suffix.keys():
            raise ValueError("CSV response histogram sets differ: " + str(prefix))
    logger.debug(
        "Found %i histogram groups for %s",
        len(paths_by_suffix),
        simulation,
    )

    state_path = run_directory / (simulation + ".gathered-chunks.txt")
    if state_path.is_file():
        gathered_entries = read_plan(state_path)
        state_mtime = state_path.stat().st_mtime_ns
    else:
        gathered_entries = []
        state_mtime = 0

    primary_events = 0
    primary_snapshots = None
    primary_paths = None
    primary_suffix = "_h1_h1.1.csv"
    if primary_suffix in paths_by_suffix:
        logger.debug("Combining %s primary histogram", simulation)
        primary_paths = paths_by_suffix.pop(primary_suffix)
        total, primary_snapshots = (
            combine_csv_histograms(
                primary_paths,
                range(1, len(prefixes) + 1),
            )
        )
        write_histogram(
            run_directory / (simulation + primary_suffix),
            total,
        )
        primary_events = int(total.entries.sum())

    convergence = []
    ionization_suffix = "_h2_h2.ion.csv"
    if ionization_suffix in paths_by_suffix and primary_snapshots is not None:
        logger.debug("Combining %s ionization histogram", simulation)
        total, convergence = (
            combine_ionization_histograms(
                run_directory,
                paths_by_suffix.pop(ionization_suffix),
                primary_snapshots,
            )
        )
        write_histogram(
            run_directory / (simulation + ionization_suffix),
            total,
        )

    for suffix, source_paths in paths_by_suffix.items():
        logger.debug("Combining %s%s", simulation, suffix)
        gather_incremental_histogram(
            gathered_entries,
            current_entries,
            state_mtime,
            source_paths,
            run_directory / (simulation + suffix),
        )

    logger.info(
        "Gathered %i completed %s runs containing %i primary events",
        len(prefixes),
        simulation,
        primary_events,
    )
    if convergence:
        write_convergence(
            run_directory / (simulation + ".convergence.csv"), convergence
        )
        log_ionization_change(simulation, convergence[-1])
    write_gathered_chunks(state_path, current_entries)
    return len(prefixes)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Combine completed AtRIS chunk histograms into canonical aggregate "
            "CSV or ROOT output and update ionization-convergence histories."
        ),
        epilog=(
            "Only chunks with .COMPLETE markers are included; partial files "
            "from failed or running chunks are ignored. Primary and ionization "
            "histograms are rebuilt to update the complete convergence history. "
            "Other CSV histograms reuse a validated aggregate and add only newly "
            "completed chunks; ROOT response histograms are rebuilt together. "
            "ROOT ntuples remain in their individual chunk files. "
            "This command does not run missing chunks, scale physical response "
            "files, or make plots. To select one species in the current "
            "directory, use an explicit dot, for example: atris-gather . "
            "protons."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        metavar="RUN_DIRECTORY",
        help="Scattered run directory (default: current directory).",
    )
    parser.add_argument(
        "simulations",
        nargs="*",
        default=("protons", "alphas"),
        metavar="SIMULATION",
        help="Simulation prefixes to gather (default: protons alphas).",
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()

    configure_logging(args.log_level)
    run_directory = args.run_directory.expanduser().resolve()
    logger.info("Starting gather in %s", run_directory)
    entries = read_chunk_plan(run_directory)
    for simulation in args.simulations:
        gather_simulation(run_directory, entries, simulation)
    log_chunk_progress(run_directory, entries, args.simulations)


def combine_root_histograms(source_paths, observe=None):
    """Add compatible ROOT histograms and concatenate available metadata."""
    total, metadata = read_root_histograms(source_paths[0])
    metadata_records = [] if metadata is None else [metadata]
    if observe is not None:
        observe(1, total, total)

    for count, path in enumerate(source_paths[1:], start=2):
        current, metadata = read_root_histograms(path)
        if current.keys() != total.keys():
            raise ValueError("ROOT response histogram sets differ: " + str(path))
        for name, histogram in current.items():
            total[name].add(histogram, "%s in %s" % (name, path))
        if metadata is not None:
            metadata_records.append(metadata)
        if observe is not None:
            observe(count, current, total)

    if not metadata_records:
        return total, None
    fields = set.intersection(*(set(record) for record in metadata_records))
    if not fields:
        return total, None
    combined_metadata = {
        name: np.concatenate([record[name] for record in metadata_records])
        for name in sorted(fields)
    }
    return total, combined_metadata


if __name__ == "__main__":
    main()
