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


logger = logging.getLogger(__name__)
RESPONSE_ENERGY_BINS = 650


def read_phantoms(run_directory):
    metadata_path = Path(run_directory) / "phantoms.txt"
    if not metadata_path.exists():
        return []

    phantoms = []
    with metadata_path.open() as metadata_file:
        for line_number, line in enumerate(metadata_file, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            columns = line.split()
            if len(columns) != 3:
                raise ValueError(
                    "Expected file stem, mass, and area at "
                    + str(metadata_path)
                    + ":"
                    + str(line_number)
                )
            try:
                mass = float(columns[1])
                area = float(columns[2])
            except ValueError as error:
                raise ValueError(
                    "Invalid phantom mass or area at "
                    + str(metadata_path)
                    + ":"
                    + str(line_number)
                ) from error
            phantoms.append(
                {
                    "stem": columns[0],
                    "mass": mass,
                    "area": area,
                }
            )
    return phantoms


def configured_phantom_files(run_directory, phantom):
    run_directory = Path(run_directory)
    stem_path = Path(phantom["stem"])
    stem = stem_path.name if stem_path.is_absolute() else str(stem_path)
    response = run_directory / (stem + "_response.txt")
    counting = run_directory / (stem + "_counting.txt")
    dummy_counting = run_directory / (stem + "_dummy_counting.txt")
    if not response.is_file():
        raise FileNotFoundError(
            "Phantom response file does not exist: " + str(response)
        )
    if counting.is_file():
        return response, counting
    if dummy_counting.is_file():
        return response, dummy_counting
    raise FileNotFoundError(
        "Phantom counting file does not exist: " + str(counting)
    )


def find_phantom_file(filename, run_directory, archive):
    path = Path(filename)
    candidates = [path] if path.is_absolute() else [run_directory / path]
    if not path.is_absolute() and archive is not None:
        candidates.append(archive / path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Phantom file does not exist: " + filename)


def _remove_numbered_links(run_directory):
    for prefix in ("radiation_phantom", "counting_phantom"):
        for path in run_directory.glob(prefix + "*.txt"):
            id_text = path.name[len(prefix) : -len(".txt")]
            if path.is_symlink() and id_text.isdigit():
                path.unlink()
                logger.debug("Removed obsolete symbolic link %s", path)


def _dummy_counting_contents(response_file):
    with response_file.open() as stream:
        header = stream.readline().strip()
    try:
        particle_codes = [int(value) for value in header.split()]
    except ValueError as error:
        raise ValueError("Invalid particle header in " + str(response_file)) from error
    if not particle_codes:
        raise ValueError("Empty particle header in " + str(response_file))

    row = " ".join(["1.000000e+00"] * RESPONSE_ENERGY_BINS) + "\n"
    return header + "\n" + row * len(particle_codes)


def _stage_file(source, destination, copy):
    if os.path.lexists(destination):
        if not destination.is_symlink():
            return False, None
        if not copy and destination.resolve() == source:
            return False, None

    previous_target = os.readlink(destination) if destination.is_symlink() else None
    if previous_target is not None:
        destination.unlink()

    try:
        if copy:
            shutil.copy2(source, destination)
            logger.debug("Copied %s to %s", source, destination)
        else:
            destination.symlink_to(os.path.relpath(source, destination.parent))
            logger.debug("Linked %s to %s", destination, source)
    except Exception:
        if previous_target is not None and not os.path.lexists(destination):
            destination.symlink_to(previous_target)
        raise
    return True, previous_target


def _stage_phantom(
    phantom,
    run_directory,
    archive,
    copy,
    accept_missing_counting,
):
    source_stem = phantom["stem"]
    source_stem_path = Path(source_stem)
    staged_stem = source_stem_path.name if source_stem_path.is_absolute() else source_stem
    response_filename = source_stem + "_response.txt"
    response_source = find_phantom_file(response_filename, run_directory, archive)
    counting_filename = source_stem + "_counting.txt"
    dummy = None
    try:
        counting_source = find_phantom_file(
            counting_filename, run_directory, archive
        )
    except FileNotFoundError:
        if not accept_missing_counting:
            raise
        counting_filename = staged_stem + "_dummy_counting.txt"
        counting_source = run_directory / counting_filename
        dummy = (counting_source, _dummy_counting_contents(response_source))

    staged_files = []
    try:
        response_destination = run_directory / (staged_stem + "_response.txt")
        changed, previous_target = _stage_file(
            response_source,
            response_destination,
            copy,
        )
        if changed:
            staged_files.append((response_destination, previous_target))

        if dummy is None:
            counting_destination = run_directory / (staged_stem + "_counting.txt")
            changed, previous_target = _stage_file(
                counting_source,
                counting_destination,
                copy,
            )
            if changed:
                staged_files.append((counting_destination, previous_target))
        else:
            destination, contents = dummy
            if not os.path.lexists(destination):
                destination.write_text(contents)
                staged_files.append((destination, None))
                logger.debug("Created dummy counting response %s", destination)
            elif destination.is_symlink():
                previous_target = os.readlink(destination)
                destination.unlink()
                destination.write_text(contents)
                staged_files.append((destination, previous_target))
                logger.debug("Created dummy counting response %s", destination)
            elif not destination.is_file() or destination.read_text() != contents:
                raise FileExistsError("Refusing to overwrite: " + str(destination))
    except Exception:
        for path, previous_target in reversed(staged_files):
            if os.path.lexists(path):
                path.unlink()
            if previous_target is not None:
                path.symlink_to(previous_target)
        raise

    if dummy is not None:
        logger.info(
            "Using dummy counting response with values of one for phantom "
            "%s: %s",
            source_stem,
            counting_source,
        )


def stage_phantoms(
    run_directory,
    archive=None,
    copy=False,
    accept_missing_counting=False,
):
    run_directory = Path(run_directory).resolve()
    if not run_directory.is_dir():
        raise FileNotFoundError("Run directory does not exist: " + str(run_directory))
    if archive is not None:
        archive = Path(archive).resolve()

    phantoms = read_phantoms(run_directory)
    _remove_numbered_links(run_directory)

    staged = 0
    for phantom in phantoms:
        try:
            _stage_phantom(
                phantom,
                run_directory,
                archive,
                copy,
                accept_missing_counting,
            )
        except (OSError, ValueError) as error:
            logger.error(
                "Could not stage phantom %s: %s",
                phantom["stem"],
                error,
            )
            continue
        staged += 1
    return staged


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Stage the phantom response and counting tables selected by "
            "phantoms.txt under their descriptive filenames."
        ),
        epilog=(
            "Each phantoms.txt row must contain file stem, mass, and area; "
            "the stem identifies the phantom. The command does not create "
            "response tables or change phantoms.txt. Symbolic links are "
            "updated to match the current selection, while regular destination "
            "files are not overwritten. An error in one row does not prevent "
            "other rows from being staged."
        ),
    )
    parser.add_argument(
        "run_directory",
        metavar="RUN_DIRECTORY",
        help="Run directory containing phantoms.txt.",
    )
    parser.add_argument(
        "--archive",
        metavar="DIRECTORY",
        help=(
            "Directory containing the named phantom tables. Files in the run "
            "directory are checked first; the default archive is "
            "$ATRIS_ROOT/phantoms when ATRIS_ROOT is set. Without either, only "
            "the run directory is searched."
        ),
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help=(
            "Copy the named phantom tables into the run directory instead of "
            "creating relative symbolic links."
        ),
    )
    parser.add_argument(
        "--accept-missing-counting",
        action="store_true",
        help=(
            "Accept a missing counting-response table by creating a local "
            "dummy table whose counting values are all one. A real counting "
            "table is always used when available."
        ),
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    archive = args.archive
    if archive is None:
        atris_root = os.environ.get("ATRIS_ROOT")
        if atris_root:
            archive = os.path.join(atris_root, "phantoms")

    count = stage_phantoms(
        args.run_directory,
        archive,
        copy=args.copy,
        accept_missing_counting=args.accept_missing_counting,
    )
    if count == 0:
        logger.info("No phantoms staged")
    else:
        method = "local copies" if args.copy else "relative symbolic links"
        logger.info(
            "Staged %i phantom%s using %s",
            count,
            "" if count == 1 else "s",
            method,
        )


if __name__ == "__main__":
    main()
