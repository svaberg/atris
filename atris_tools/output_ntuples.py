"""Read and write the small metadata ntuples emitted by AtRIS."""

import csv
import os
from pathlib import Path
import re
import tempfile

import numpy as np

METADATA_SCHEMA = (
    ("int", "schema"),
    ("string", "atris_version"),
    ("string", "input_prefix"),
    ("string", "physics_list"),
    ("string", "output_mode"),
    ("int", "phantom_count"),
    ("int", "seeds_explicit"),
    ("int", "random_seed_1"),
    ("int", "random_seed_2"),
)
RESPONSE_SCHEMA = (
    ("string", "phantom_stem"),
    ("string", "name"),
    ("string", "file"),
    ("int", "scale_by_crossing_energy"),
    ("int", "scale_by_radiation_weight"),
    ("int", "scale_by_inverse_phantom_mass"),
)


def _paths(prefix, name):
    prefix = Path(prefix)
    canonical = prefix.with_name(prefix.name + "_nt_" + name + ".csv")
    if canonical.is_file():
        return [canonical]
    pattern = re.compile(
        "^" + re.escape(prefix.name) + "_nt_" + re.escape(name) + r"(?:_t\d+)?\.csv$"
    )
    return sorted(
        path
        for path in prefix.parent.glob(prefix.name + "_nt_" + name + "*.csv")
        if pattern.match(path.name)
    )


def _dtype(value_type):
    try:
        return {"int": int, "float": float, "double": float, "string": str}[value_type]
    except KeyError as error:
        raise ValueError(
            "Unsupported Geant4 ntuple column type: " + value_type
        ) from error


def read_csv_ntuple(prefix, name, schema, *, required=True):
    """Read one logical Geant4 CSV ntuple, including thread-suffixed files."""
    paths = _paths(prefix, name)
    if not paths:
        if required:
            raise FileNotFoundError("No %s ntuple found for %s" % (name, prefix))
        return {
            column_name: np.array([], dtype=_dtype(value_type))
            for value_type, column_name in schema
        }

    expected_columns = ["#column %s %s" % column for column in schema]
    rows = []
    for path in paths:
        lines = path.read_text().splitlines()
        columns = [line for line in lines if line.startswith("#column ")]
        if columns != expected_columns:
            raise ValueError("Unexpected %s ntuple columns in %s" % (name, path))
        for row in csv.reader(line for line in lines if not line.startswith("#")):
            if len(row) != len(schema):
                raise ValueError("Unexpected %s ntuple row in %s" % (name, path))
            rows.append(
                tuple(
                    _dtype(value_type)(value)
                    for value, (value_type, _) in zip(row, schema)
                )
            )

    return {
        column_name: np.asarray(
            [row[index] for row in rows],
            dtype=_dtype(value_type),
        )
        for index, (value_type, column_name) in enumerate(schema)
    }


def combine_records(records, *, unique=False):
    """Concatenate compatible column dictionaries, optionally removing duplicate rows."""
    if not records:
        return None
    columns = tuple(
        name for name in records[0] if all(name in record for record in records[1:])
    )
    if not columns:
        return None
    combined = {
        name: np.concatenate([record[name] for record in records]) for name in columns
    }
    if not unique or not combined:
        return combined

    rows = list(dict.fromkeys(zip(*(values.tolist() for values in combined.values()))))
    return {
        name: np.asarray([row[index] for row in rows], dtype=values.dtype)
        for index, (name, values) in enumerate(combined.items())
    }


def write_csv_ntuple(path, title, schema, columns):
    """Write a small Geant4-compatible CSV ntuple atomically."""
    path = Path(path)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
            newline="",
        ) as output:
            temporary_name = output.name
            output.write("#class tools::wcsv::ntuple\n")
            output.write("#title " + title + "\n")
            output.write("#separator 44\n")
            output.write("#vector_separator 59\n")
            for value_type, name in schema:
                output.write("#column %s %s\n" % (value_type, name))
            writer = csv.writer(output, lineterminator="\n")
            writer.writerows(zip(*(columns[name] for _, name in schema)))
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)
