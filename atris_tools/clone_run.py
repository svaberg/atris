"""Clone reusable AtRIS inputs without copying simulation results."""

import argparse
import logging
import os
import shutil
from pathlib import Path

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)


INPUT_NAMES = (
    "simulation.psf",
    "phantoms.txt",
    "nrlmsis_output.txt",
)

INPUT_PATTERNS = (
    "*.gdml",
    "*.mac",
    "*.bins",
    "*.spec",
    "*_response.txt",
    "*_counting.txt",
)
logger = logging.getLogger(__name__)


def find_run_inputs(run_directory):
    inputs = {}
    for name in INPUT_NAMES:
        path = run_directory / name
        if path.is_file() or path.is_symlink():
            inputs[path.name] = path
    for pattern in INPUT_PATTERNS:
        for path in run_directory.glob(pattern):
            if path.is_file() or path.is_symlink():
                inputs[path.name] = path
    return [inputs[name] for name in sorted(inputs)]


def clone_run(source_directory, destination_directory):
    source_directory = Path(source_directory).expanduser().resolve()
    destination_directory = Path(destination_directory).expanduser().resolve()

    if not source_directory.is_dir():
        raise FileNotFoundError(
            "Source run directory does not exist: " + str(source_directory)
        )
    if os.path.lexists(destination_directory):
        raise FileExistsError(
            "Destination already exists: " + str(destination_directory)
        )

    inputs = find_run_inputs(source_directory)
    if not inputs:
        raise ValueError("No AtRIS input files found in " + str(source_directory))

    destination_directory.mkdir()
    created = []
    try:
        for source in inputs:
            destination = destination_directory / source.name
            created.append(destination)
            if source.is_symlink():
                target = source.resolve(strict=True)
                try:
                    relative_target = target.relative_to(source_directory)
                except ValueError:
                    destination_target = target
                else:
                    destination_target = destination_directory / relative_target
                destination.symlink_to(
                    os.path.relpath(destination_target, destination_directory)
                )
            else:
                shutil.copy2(source, destination)
            logger.debug("Cloned input %s", source.name)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        destination_directory.rmdir()
        raise

    return [path.name for path in inputs]


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Create a new AtRIS run directory from the reusable inputs in an "
            "existing run."
        ),
        epilog=(
            "Simulation results, chunk plans, completion markers, and logs are "
            "not copied. The destination must not already exist. Symbolic "
            "links among copied inputs are preserved and rebased when their "
            "targets are also inside the source run. This command prepares a "
            "starting point; it does not run or scatter the simulation."
        ),
    )
    parser.add_argument(
        "source",
        metavar="SOURCE",
        help="Existing run directory containing reusable AtRIS inputs.",
    )
    parser.add_argument(
        "destination",
        metavar="DESTINATION",
        help="New run directory to create.",
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    copied = clone_run(args.source, args.destination)
    logger.info(
        "Cloned %i input files to %s",
        len(copied),
        Path(args.destination).expanduser().resolve(),
    )


if __name__ == "__main__":
    main()
