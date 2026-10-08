"""Dump an AtRIS ROOT ntuple as CSV text."""

import argparse
import csv
import os
from pathlib import Path
import sys

from .cli import HelpFormatter, add_version_argument
from .root_output import iterate_ntuple, ntuple_fields

NTUPLES = ("interfaces", "steps")


def _csv_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "item"):
        return value.item()
    return value


def dump_ntuple(path, ntuple, stream):
    """Stream one AtRIS ROOT ntuple as CSV."""
    fields = ntuple_fields(path, ntuple)
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(fields)

    for records in iterate_ntuple(path, ntuple, fields):
        for record in records:
            writer.writerow([_csv_value(record[field]) for field in fields])


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Dump an AtRIS interface or transport-step ROOT ntuple as CSV "
            "text on standard output."
        ),
        epilog=(
            "The ROOT file is read incrementally and is not modified. Pipe "
            "the output to tools such as head or redirect it to a text file."
        ),
    )
    parser.add_argument(
        "root_file",
        type=Path,
        metavar="ROOT_FILE",
        help="AtRIS mode-0 or mode-1 ROOT file to read.",
    )
    parser.add_argument(
        "ntuple",
        choices=NTUPLES,
        metavar="{interfaces,steps}",
        help="ROOT ntuple to dump.",
    )
    add_version_argument(parser)
    args = parser.parse_args()

    try:
        dump_ntuple(args.root_file, args.ntuple, sys.stdout)
        sys.stdout.flush()
    except BrokenPipeError:
        sys.stdout = open(os.devnull, "w")
    return 0


if __name__ == "__main__":
    main()
