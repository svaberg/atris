"""Gather completed AtRIS repetitions into canonical histogram files."""

import argparse
from contextlib import contextmanager
import logging
import math
import os
from pathlib import Path
import tempfile

import numpy as np

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)
from .output_ntuples import (
    METADATA_SCHEMA,
    RESPONSE_SCHEMA,
    combine_records,
    read_csv_ntuple,
    write_csv_ntuple,
)
from .postprocess import process_psf
from .response_histograms import (
    IONIZATION_HISTOGRAM,
    PRIMARY_HISTOGRAM,
    csv_histogram_axes,
    read_csv_histogram,
    response_output_format,
    table_histogram_values,
)
from .root_histograms import (
    combine_root_histograms,
    write_root_histograms,
)

PLANE_SUM_PREFIX = "#planes_Sxyw "
ETA_COMPLETION_WINDOW = 20
CHANGE_FRACTION = 0.1
CONVERGENCE_COLUMNS = (
    "completed_chunks,primary_events,comparison_chunks,"
    "comparison_percent,ionization_change_percent,"
    "cell_change_p50_percent,cell_change_p90_percent,"
    "cell_relative_se_p50_percent,cell_relative_se_p90_percent"
)
logger = logging.getLogger(__name__)


@contextmanager
def atomic_text_output(path):
    """Yield a temporary text file and replace path after a successful write."""
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary_name = output.name
            yield output
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def read_plan(path):
    """Read simulation and seed triples from a chunk-plan file."""
    entries = []
    with path.open() as plan:
        for line_number, line in enumerate(plan, start=1):
            fields = line.split()
            if len(fields) != 3:
                raise ValueError("Invalid %s line %i" % (path.name, line_number))
            simulation, seed1, seed2 = fields
            entries.append((simulation, seed1, seed2))
    return entries


def read_chunk_plan(run_directory):
    return read_plan(run_directory / "chunks.txt")


def chunk_name(entry):
    """Return the output-prefix name for one chunk-plan entry."""
    return "%s_%s_%s" % entry


def complete_entries(run_directory, entries, simulation):
    chunks_directory = run_directory / "chunks"
    return [
        entry
        for entry in entries
        if entry[0] == simulation
        and (chunks_directory / (chunk_name(entry) + ".COMPLETE")).is_file()
    ]


def chunk_progress(run_directory, entries, simulations):
    """Return completion counts, interval, and estimated remaining seconds."""
    simulations = set(simulations)
    markers = []
    total = 0
    chunks_directory = run_directory / "chunks"
    for entry in entries:
        simulation = entry[0]
        if simulation not in simulations:
            continue
        total += 1
        marker = chunks_directory / (chunk_name(entry) + ".COMPLETE")
        if marker.is_file():
            markers.append(marker)

    completed = len(markers)
    if completed < 2:
        remaining_seconds = 0 if completed == total else None
        return completed, total, None, remaining_seconds

    completion_times = sorted(marker.stat().st_mtime for marker in markers)
    recent_times = completion_times[-ETA_COMPLETION_WINDOW:]
    seconds_per_chunk = (recent_times[-1] - recent_times[0]) / (len(recent_times) - 1)
    return (
        completed,
        total,
        seconds_per_chunk,
        seconds_per_chunk * (total - completed),
    )


def format_duration(seconds):
    """Format a duration for a compact progress message."""
    seconds = max(0, round(seconds))
    days, seconds = divmod(seconds, 24 * 60 * 60)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return "%id %ih" % (days, hours)
    if hours:
        return "%ih %im" % (hours, minutes)
    if minutes:
        return "%im %is" % (minutes, seconds)
    return "%is" % seconds


def log_chunk_progress(run_directory, entries, simulations):
    """Log chunk completion progress and an ETA when one is available."""
    completed, total, completion_interval, remaining_seconds = chunk_progress(
        run_directory, entries, simulations
    )
    if completed == total:
        if completion_interval is None:
            logger.info("Chunk progress: %i/%i complete.", completed, total)
        else:
            logger.info(
                "Chunk progress: %i/%i complete; average completion interval %s.",
                completed,
                total,
                format_duration(completion_interval),
            )
    elif remaining_seconds is None:
        logger.info(
            "Chunk progress: %i/%i complete; ETA available after two completions.",
            completed,
            total,
        )
    else:
        logger.info(
            "Chunk progress: %i/%i complete; average completion interval %s; "
            "estimated time remaining %s.",
            completed,
            total,
            format_duration(completion_interval),
            format_duration(remaining_seconds),
        )


def read_histogram(path):
    return read_csv_histogram(path)


def comparable_header(header):
    return [line for line in header if not line.startswith(PLANE_SUM_PREFIX)]


def plane_sum(header):
    for line in header:
        if line.startswith(PLANE_SUM_PREFIX):
            return float(line[len(PLANE_SUM_PREFIX) :])
    return None


def write_histogram(path, header, columns, data, total_plane_sum):
    output_header = list(header)
    if total_plane_sum is not None:
        for index, line in enumerate(output_header):
            if line.startswith(PLANE_SUM_PREFIX):
                output_header[index] = PLANE_SUM_PREFIX + "%.17g" % total_plane_sum

    with atomic_text_output(path) as output:
        for line in output_header:
            output.write(line + "\n")
        output.write(columns + "\n")
        formats = ["%.0f"] + ["%.17g"] * (data.shape[1] - 1)
        np.savetxt(output, data, delimiter=",", fmt=formats)


def write_gathered_chunks(path, entries):
    """Write the gathered subset of chunks.txt atomically."""
    with atomic_text_output(path) as output:
        for entry in entries:
            output.write("%s %s %s\n" % entry)


def combine_histograms(source_paths, snapshot_counts=(), observe=None):
    snapshot_counts = set(snapshot_counts)
    first_header, first_columns, total = read_histogram(source_paths[0])
    total_plane_sum = plane_sum(first_header)
    snapshots = {1: total.copy()} if 1 in snapshot_counts else {}
    if observe is not None:
        observe(1, total, total)

    for source_number, source_path in enumerate(source_paths[1:], start=2):
        header, columns, data = read_histogram(source_path)
        if comparable_header(header) != comparable_header(first_header):
            raise ValueError("Histogram headers differ: " + str(source_path))
        if columns != first_columns or data.shape != total.shape:
            raise ValueError("Histogram shape differs: " + str(source_path))
        total += data
        current_plane_sum = plane_sum(header)
        if (total_plane_sum is None) != (current_plane_sum is None):
            raise ValueError("Histogram headers differ: " + str(source_path))
        if total_plane_sum is not None:
            total_plane_sum += current_plane_sum
        if source_number in snapshot_counts:
            snapshots[source_number] = total.copy()
        if observe is not None:
            observe(source_number, data, total)

    return first_header, first_columns, total, total_plane_sum, snapshots


def gather_histogram(source_paths, destination):
    header, columns, total, total_plane_sum, _ = combine_histograms(source_paths)

    write_histogram(destination, header, columns, total, total_plane_sum)
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
        path.stat().st_mtime_ns > output_mtime for path in source_paths[:gathered_count]
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


def ionization_components(primary_energy, ionization):
    """Return primary counts and ionization sums for plotted detector cells."""
    primary_counts = primary_energy[1:-1]
    return primary_counts, ionization[1:-1, 2:-2].T


def ionization_response(primary_energy, ionization, geometry):
    """Return the ionization matrix displayed by the quick-look plot."""
    primary_counts, ionization_sum = ionization_components(primary_energy, ionization)
    with np.errstate(divide="ignore", invalid="ignore"):
        response = ionization_sum / primary_counts[None, :]
        response = response / geometry["volume/cm3"][1:-1, None]
    return response


def fractional_change(previous, current):
    """Return symmetric fractional change between two nonnegative arrays."""
    previous = np.nan_to_num(previous, nan=0.0, posinf=0.0, neginf=0.0)
    current = np.nan_to_num(current, nan=0.0, posinf=0.0, neginf=0.0)
    denominator = np.sum(np.abs(previous) + np.abs(current))
    if denominator == 0:
        return 0.0
    return np.sum(np.abs(current - previous)) / denominator


def cell_change_percentiles(previous, current):
    """Return median and 90th-percentile fractional changes across cells."""
    previous = np.nan_to_num(previous, nan=0.0, posinf=0.0, neginf=0.0)
    current = np.nan_to_num(current, nan=0.0, posinf=0.0, neginf=0.0)
    denominator = np.abs(previous) + np.abs(current)
    changed = denominator > 0
    values = np.abs(current[changed] - previous[changed]) / denominator[changed]
    return finite_percentiles(values)


def finite_percentiles(values):
    """Return median and 90th percentile after excluding undefined cells."""
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    if not values.size:
        return np.array([np.nan, np.nan])
    return np.percentile(values, (50, 90))


def change_reference_count(completed_count):
    """Return the chunk count before the final comparison fraction."""
    if completed_count < 2:
        return None
    comparison_count = max(1, math.ceil(CHANGE_FRACTION * completed_count))
    return completed_count - comparison_count


def ionization_convergence_observer(run_directory, completed_count, primary_snapshots):
    """Return an observer that calculates convergence after every chunk."""
    geometry, _ = process_psf(run_directory / "simulation.psf")
    references = {
        count: change_reference_count(count) for count in range(2, completed_count + 1)
    }
    last_use = {}
    for count, reference in references.items():
        last_use[reference] = count

    stored_responses = {}
    rows = []
    weights = None
    mean = None
    squared_residuals = None
    contributing_chunks = None

    def observe(count, ionization_chunk, ionization_total):
        nonlocal weights, mean, squared_residuals, contributing_chunks
        primary_total = primary_snapshots[count]
        if count == 1:
            primary_chunk = primary_total
        else:
            primary_chunk = primary_total - primary_snapshots[count - 1]

        chunk_counts, chunk_sum = ionization_components(primary_chunk, ionization_chunk)
        if weights is None:
            weights = np.zeros(chunk_counts.shape)
            mean = np.zeros(chunk_sum.shape)
            squared_residuals = np.zeros(chunk_sum.shape)
            contributing_chunks = np.zeros(chunk_counts.shape, dtype=int)

        chunk_mean = np.zeros(chunk_sum.shape)
        np.divide(
            chunk_sum,
            chunk_counts[None, :],
            out=chunk_mean,
            where=chunk_counts[None, :] > 0,
        )
        new_weights = weights + chunk_counts
        delta = chunk_mean - mean
        fraction = np.zeros(chunk_counts.shape)
        np.divide(
            chunk_counts,
            new_weights,
            out=fraction,
            where=new_weights > 0,
        )
        new_mean = mean + delta * fraction[None, :]
        squared_residuals += chunk_counts[None, :] * delta * (chunk_mean - new_mean)
        contributing_chunks += chunk_counts > 0
        weights = new_weights
        mean = new_mean

        current = ionization_response(
            primary_total,
            ionization_total,
            geometry,
        )
        if count >= 2:
            reference_count = references[count]
            reference = stored_responses[reference_count]
            comparison_chunks = count - reference_count
            cell_change = 100.0 * cell_change_percentiles(reference, current)
            with np.errstate(divide="ignore", invalid="ignore"):
                variance = (
                    np.maximum(squared_residuals, 0.0)
                    / (contributing_chunks - 1)[None, :]
                )
                standard_error = np.sqrt(variance / weights[None, :])
                relative_error = standard_error / np.abs(mean)
            cell_uncertainty = 100.0 * finite_percentiles(relative_error)
            rows.append(
                (
                    count,
                    int(primary_total[1:-1].sum()),
                    comparison_chunks,
                    100.0 * comparison_chunks / count,
                    100.0 * fractional_change(reference, current),
                    cell_change[0],
                    cell_change[1],
                    cell_uncertainty[0],
                    cell_uncertainty[1],
                )
            )
            if last_use[reference_count] == count:
                del stored_responses[reference_count]
        if count in last_use:
            stored_responses[count] = current

    return observe, rows


def combine_ionization_histograms(run_directory, source_paths, primary_snapshots):
    """Combine ionization files and calculate convergence after every chunk."""
    observe_values, rows = ionization_convergence_observer(
        run_directory, len(source_paths), primary_snapshots
    )
    axes = csv_histogram_axes(source_paths[0])

    def observe(count, current, total):
        observe_values(
            count,
            table_histogram_values(current, axes),
            table_histogram_values(total, axes),
        )

    header, columns, total, total_plane_sum, _ = combine_histograms(
        source_paths, observe=observe
    )
    return header, columns, total, total_plane_sum, rows


def write_convergence(path, rows):
    """Write an ionization convergence table atomically."""
    with atomic_text_output(path) as output:
        output.write(CONVERGENCE_COLUMNS + "\n")
        np.savetxt(
            output,
            rows,
            delimiter=",",
            fmt=("%i", "%i", "%i") + ("%.17g",) * 6,
        )


def log_ionization_change(simulation, row):
    """Report the final ionization convergence row."""
    completed_count, _, comparison_chunks, comparison_percent, change = row[:5]
    species = {"protons": "Proton", "alphas": "Alpha"}[simulation]
    logger.info(
        "%s ionization change after final %i of %i completed chunks "
        "(%.1f%%): %.2f%%",
        species,
        comparison_chunks,
        completed_count,
        comparison_percent,
        change,
    )


def gather_csv_ntuples(run_directory, prefixes, simulation):
    """Gather the metadata ntuples shared by CSV and ROOT output."""
    metadata = combine_records(
        [read_csv_ntuple(prefix, "metadata", METADATA_SCHEMA) for prefix in prefixes]
    )
    responses = combine_records(
        [
            read_csv_ntuple(prefix, "responses", RESPONSE_SCHEMA, required=False)
            for prefix in prefixes
        ],
        unique=True,
    )
    write_csv_ntuple(
        run_directory / (simulation + "_nt_metadata.csv"),
        "AtRIS output metadata",
        METADATA_SCHEMA,
        metadata,
    )
    write_csv_ntuple(
        run_directory / (simulation + "_nt_responses.csv"),
        "AtRIS phantom response definitions",
        RESPONSE_SCHEMA,
        responses,
    )


def gather_root_simulation(run_directory, current_entries, prefixes, simulation):
    """Gather response histograms from ROOT chunks, leaving ntuples sharded."""
    source_paths = [Path(str(prefix) + ".root") for prefix in prefixes]
    primary_snapshots = {}
    convergence = []
    convergence_observer = None

    def observe(count, current, total):
        nonlocal convergence_observer, convergence
        primary_snapshots[count] = total[PRIMARY_HISTOGRAM]["values"].copy()
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
            current[IONIZATION_HISTOGRAM]["values"],
            total[IONIZATION_HISTOGRAM]["values"],
        )

    histograms, metadata, responses = combine_root_histograms(
        source_paths, observe=observe
    )
    primary = histograms[PRIMARY_HISTOGRAM]
    primary_events = primary["statistics"]["fEntries"]
    if not np.isclose(primary["values"].sum(), primary_events):
        raise ValueError(
            "%s ROOT chunks contain weighted %s histograms; per-bin primary "
            "counts are unavailable" % (simulation, PRIMARY_HISTOGRAM)
        )

    write_root_histograms(
        run_directory / (simulation + ".root"),
        histograms,
        metadata,
        responses,
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
    prefixes = [chunks_directory / chunk_name(entry) for entry in current_entries]
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

    histogram_paths = sorted(first_prefix.parent.glob(first_prefix.name + "_h*.csv"))
    if not histogram_paths:
        raise FileNotFoundError(
            "Completed run has no histogram files: " + str(first_prefix)
        )

    paths_by_suffix = {}
    for first_path in histogram_paths:
        suffix = first_path.name[len(first_prefix.name) :]
        source_paths = [prefix.parent / (prefix.name + suffix) for prefix in prefixes]
        for source_path in source_paths:
            if not source_path.is_file():
                raise FileNotFoundError(
                    "Missing histogram from completed run: " + str(source_path)
                )
        paths_by_suffix[suffix] = source_paths
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
        header, columns, total, total_plane_sum, primary_snapshots = combine_histograms(
            primary_paths,
            range(1, len(prefixes) + 1),
        )
        write_histogram(
            run_directory / (simulation + primary_suffix),
            header,
            columns,
            total,
            total_plane_sum,
        )
        primary_events = int(total[:, 0].sum())

    convergence = []
    ionization_suffix = "_h2_h2.ion.csv"
    if ionization_suffix in paths_by_suffix and primary_snapshots is not None:
        logger.debug("Combining %s ionization histogram", simulation)
        primary_axes = csv_histogram_axes(primary_paths[0])
        primary_snapshots = {
            count: table_histogram_values(snapshot, primary_axes, 0)
            for count, snapshot in primary_snapshots.items()
        }
        header, columns, total, total_plane_sum, convergence = (
            combine_ionization_histograms(
                run_directory,
                paths_by_suffix.pop(ionization_suffix),
                primary_snapshots,
            )
        )
        write_histogram(
            run_directory / (simulation + ionization_suffix),
            header,
            columns,
            total,
            total_plane_sum,
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

    gather_csv_ntuples(run_directory, prefixes, simulation)
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
            "ROOT interface and step ntuples remain in their chunk files. "
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


if __name__ == "__main__":
    main()
