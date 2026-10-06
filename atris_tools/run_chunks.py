"""Run incomplete entries from an AtRIS chunk plan."""

import argparse
import logging
from pathlib import Path
import subprocess
import tempfile
import time

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)
from .gather import chunk_name, read_chunk_plan
from .phantoms import configured_phantom_files, read_phantoms


logger = logging.getLogger(__name__)


def chunk_wrapper(run_directory, species, run_name, first_seed, second_seed):
    """Write a temporary macro that supplies one chunk's execution settings."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=run_directory,
        prefix=".atris-chunk-",
        suffix=".mac",
        delete=False,
    ) as wrapper:
        wrapper.write(
            "/control/alias ATRIS_OUTPUT_FILE chunks/%s\n"
            "/control/alias ATRIS_SEED_1 %s\n"
            "/control/alias ATRIS_SEED_2 %s\n"
            "/control/execute %s.chunk.mac\n"
            % (run_name, first_seed, second_seed, species)
        )
    return Path(wrapper.name)


def format_estimated_time(minutes):
    """Format an estimated remaining time in minutes or hours."""
    if minutes < 60:
        return "%.1f min" % minutes
    return "%.1f h" % (minutes / 60)


def worker_label(worker_index, worker_count):
    """Return a space-aligned label when several workers share a run."""
    if worker_count == 1:
        return ""
    number = str(worker_index + 1).rjust(len(str(worker_count)))
    return "Worker %s/%i" % (number, worker_count)


def chunk_label(worker, chunk_number, chunk_count):
    """Return a consistently aligned worker and chunk progress label."""
    number = str(chunk_number).rjust(len(str(chunk_count)))
    chunk = "chunk %s/%i" % (number, chunk_count)
    if worker:
        return "%s %s" % (worker, chunk)
    return chunk.capitalize()


def select_entries(entries, entry=None, worker_index=0, worker_count=1):
    """Select one entry or the round-robin shard assigned to a worker."""
    if worker_count < 1:
        raise ValueError("Worker count must be at least 1")
    if worker_index < 0 or worker_index >= worker_count:
        raise ValueError(
            "Worker index must be between 0 and %i" % (worker_count - 1)
        )
    if entry is not None:
        if entry < 1 or entry > len(entries):
            raise ValueError("Chunk entry must be between 1 and %i" % len(entries))
        return [(entry, entries[entry - 1])]
    return [
        (line_number, plan_entry)
        for line_number, plan_entry in enumerate(entries, start=1)
        if (line_number - 1) % worker_count == worker_index
    ]


def incomplete_entry_numbers(run_directory):
    """Return one-based plan entries without completion markers."""
    run_directory = Path(run_directory).expanduser().resolve()
    entries = read_chunk_plan(run_directory)
    chunks_directory = run_directory / "chunks"
    return [
        line_number
        for line_number, plan_entry in enumerate(entries, start=1)
        if not (chunks_directory / (chunk_name(plan_entry) + ".COMPLETE")).is_file()
    ]


def run_chunks(
    run_directory,
    entry=None,
    worker_index=0,
    worker_count=1,
    deadline=None,
    stop_before_end=0,
    clock=time.time,
    timer=time.monotonic,
):
    """Run incomplete chunks and mark each successful run as complete."""
    run_directory = Path(run_directory).expanduser().resolve()
    entries = read_chunk_plan(run_directory)
    selected_entries = select_entries(
        entries,
        entry=entry,
        worker_index=worker_index,
        worker_count=worker_count,
    )
    worker = worker_label(worker_index, worker_count)
    prefix = worker + ": " if worker else ""
    if stop_before_end < 0:
        raise ValueError("Stop-before-end interval cannot be negative")
    if stop_before_end and deadline is None:
        raise ValueError("Stop-before-end interval requires a job deadline")

    phantoms = read_phantoms(run_directory)
    phantom_count = len(phantoms)
    logger.info("%sStarting AtRIS chunked run", prefix)
    logger.info("%sRun directory: %s", prefix, run_directory)
    logger.info("%sChunk plan: %s", prefix, run_directory / "chunks.txt")
    for phantom_number, phantom in enumerate(phantoms, start=1):
        phantom_label = "Phantom %i/%i" % (phantom_number, phantom_count)
        response_path, counting_path = configured_phantom_files(
            run_directory,
            phantom,
        )
        response_path = response_path.resolve()
        counting_path = counting_path.resolve()
        logger.info("%s%s: %s", prefix, phantom_label, phantom["stem"])
        logger.debug(
            "%s%s counting file: %s",
            prefix,
            phantom_label,
            counting_path,
        )
        logger.debug(
            "%s%s response file: %s",
            prefix,
            phantom_label,
            response_path,
        )
    logger.info("%sProcessing %i chunks...", prefix, len(selected_entries))

    pending_entries = []
    for line_number, plan_entry in selected_entries:
        run_name = chunk_name(plan_entry)
        complete = run_directory / "chunks" / (run_name + ".COMPLETE")
        if complete.is_file():
            logger.debug(
                "%s complete: %s",
                chunk_label(worker, line_number, len(entries)),
                Path("chunks") / run_name,
            )
        else:
            pending_entries.append((line_number, plan_entry))

    pending_count = len(pending_entries)
    finished_count = len(selected_entries) - pending_count
    finished_noun = "chunk" if finished_count == 1 else "chunks"
    pending_noun = "chunk" if pending_count == 1 else "chunks"
    logger.info(
        "%s%i/%i %s already processed",
        prefix,
        finished_count,
        len(selected_entries),
        finished_noun,
    )
    logger.info(
        "%sProcessing remaining %i/%i %s...",
        prefix,
        pending_count,
        len(selected_entries),
        pending_noun,
    )
    completed = 0
    elapsed_minutes = 0
    for line_number, plan_entry in pending_entries:
        run_name = chunk_name(plan_entry)
        complete = run_directory / "chunks" / (run_name + ".COMPLETE")
        progress = chunk_label(worker, line_number, len(entries))

        if deadline is not None and clock() >= deadline - stop_before_end:
            logger.info(
                "%s not started because "
                "the wall-time safety window has begun",
                progress,
            )
            break

        log_path = run_directory / "chunks" / (run_name + ".log")
        chunk_stem = str(Path("chunks") / run_name)
        logger.debug(
            "%s starting: %s",
            progress,
            chunk_stem,
        )
        started = timer()
        species, first_seed, second_seed = plan_entry
        wrapper = chunk_wrapper(
            run_directory,
            species,
            run_name,
            first_seed,
            second_seed,
        )
        try:
            with log_path.open("w") as log:
                subprocess.run(
                    ["AtRIS", wrapper.name],
                    cwd=run_directory,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
        finally:
            wrapper.unlink(missing_ok=True)
        complete.touch()
        completed += 1
        chunk_minutes = (timer() - started) / 60
        elapsed_minutes += chunk_minutes
        estimated_minutes = (
            elapsed_minutes / completed * (pending_count - completed)
        )
        estimated_time = format_estimated_time(estimated_minutes)
        logger.info(
            "%s complete in %.1f min. ETA: %s",
            progress,
            chunk_minutes,
            estimated_time,
        )

    remaining_count = pending_count - completed
    finished_total = finished_count + completed
    status = "finished" if remaining_count == 0 else "stopped"
    completed_noun = "chunk" if completed == 1 else "chunks"
    remaining_noun = "chunk" if remaining_count == 1 else "chunks"
    logger.info("%sAtRIS chunk run %s", prefix, status)
    logger.info(
        "%sCompleted %i new %s in %s",
        prefix,
        completed,
        completed_noun,
        format_estimated_time(elapsed_minutes),
    )
    logger.info(
        "%sFinished chunks: %i/%i",
        prefix,
        finished_total,
        len(selected_entries),
    )
    logger.info(
        "%sRemaining: %i %s",
        prefix,
        remaining_count,
        remaining_noun,
    )

    return completed


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run the incomplete entries assigned to one worker from an AtRIS "
            "chunk plan, marking each successful chunk complete."
        ),
        formatter_class=HelpFormatter,
        epilog=(
            "The command reads chunks.txt, uses phantoms.txt when present for "
            "progress labels, skips entries with an existing .COMPLETE marker, "
            "and runs selected entries sequentially. Worker coordinates select "
            "a collision-free shard; "
            "they do not launch workers or control Geant4 threads. A deadline "
            "is checked only before a chunk starts and never interrupts a "
            "running chunk. Failed chunks are left incomplete. Each species "
            "macro selects its physics list, output mode, and other run "
            "settings. This command does not gather or post-process results."
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
    chunk_options = parser.add_argument_group("Chunk plan and worker options")
    chunk_options.add_argument(
        "--entry",
        type=int,
        metavar="NUMBER",
        help=(
            "Run only this one-based chunks.txt entry instead of a worker "
            "shard. A completed entry is still skipped."
        ),
    )
    chunk_options.add_argument(
        "--worker-index",
        type=int,
        metavar="INDEX",
        help=(
            "Zero-based rank used to select this worker's round-robin shard; "
            "must be supplied with --worker-count (default: 0)."
        ),
    )
    chunk_options.add_argument(
        "--worker-count",
        type=int,
        metavar="COUNT",
        help=(
            "Number of externally launched workers sharing the plan; must be "
            "supplied with --worker-index (default: 1)."
        ),
    )
    chunk_options.add_argument(
        "--stop-before-end",
        type=int,
        default=0,
        metavar="SECONDS",
        help=(
            "Do not start another chunk within SECONDS of --deadline "
            "(default: 0)."
        ),
    )
    chunk_options.add_argument(
        "--deadline",
        type=float,
        metavar="UNIX_TIME",
        help=(
            "Absolute Unix timestamp at which the external allocation ends; "
            "used only with --stop-before-end."
        ),
    )
    chunk_options.add_argument(
        "--check-complete",
        action="store_true",
        help=(
            "Do not run anything; return success only when every chunks.txt "
            "entry has a completion marker."
        ),
    )
    logging_options = parser.add_argument_group("Logging options")
    add_logging_arguments(logging_options)

    parser.add_argument_group(
        "Examples",
        description=(
            "atris-run runs/earth\n"
            "  Run every incomplete chunk sequentially.\n"
            "\n"
            "G4FORCENUMBEROFTHREADS=7 atris-run runs/earth \\\n"
            "  --worker-index 2 --worker-count 11 \\\n"
            "  --deadline \"$JOB_END_TIME\" --stop-before-end 1800\n"
            "  Run worker index 2's round-robin shard of an 11-worker pool with "
            "seven Geant4 threads. It does not start a new chunk during the "
            "allocation's final 30 minutes. Launch the other worker indices "
            "externally.\n"
            "\n"
            "atris-run runs/earth --entry 17\n"
            "  Run only plan entry 17 unless it is already complete.\n"
            "\n"
            "atris-run runs/earth --check-complete\n"
            "  Check whether every planned chunk has a completion marker."
        ),
    )
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    if args.check_complete:
        incomplete = incomplete_entry_numbers(args.run_directory)
        if incomplete:
            preview = ", ".join(str(number) for number in incomplete[:20])
            if len(incomplete) > 20:
                preview += ", ..."
            logger.warning(
                "Chunk plan is incomplete: %i entries remain (%s)",
                len(incomplete),
                preview,
            )
            return 1
        logger.info("Chunk plan is complete")
        return 0

    if args.worker_index is None and args.worker_count is None:
        worker_index, worker_count = 0, 1
    elif (args.worker_index is None) != (args.worker_count is None):
        parser.error("--worker-index and --worker-count must be supplied together")
    else:
        worker_index, worker_count = args.worker_index, args.worker_count

    run_chunks(
        args.run_directory,
        entry=args.entry,
        worker_index=worker_index,
        worker_count=worker_count,
        deadline=args.deadline,
        stop_before_end=args.stop_before_end,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
