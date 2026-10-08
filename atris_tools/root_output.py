"""Read ntuples written by Geant4's ROOT analysis backend."""

from pathlib import Path

import numpy as np
import uproot


def _tree(root_file, tree_name, field_names):
    if tree_name not in root_file:
        raise ValueError(
            "%s does not contain the %s ntuple"
            % (Path(root_file.file_path).name, tree_name)
        )
    tree = root_file[tree_name]
    missing = [name for name in field_names if name not in tree]
    if missing:
        raise ValueError(
            "%s ntuple is missing columns: %s" % (tree_name, ", ".join(missing))
        )
    return tree


def _structured_records(arrays, field_names):
    columns = [np.asarray(arrays[name]) for name in field_names]
    size = len(columns[0]) if columns else 0
    dtype = [
        (name, object if values.dtype.kind == "O" else values.dtype)
        for name, values in zip(field_names, columns)
    ]
    records = np.empty(size, dtype=dtype)
    for name, values in zip(field_names, columns):
        records[name] = values
    return records


def read_ntuple(filename, tree_name, field_names):
    """Read a complete Geant4 ROOT ntuple into a structured array."""
    path = Path(filename)
    with uproot.open(path) as root_file:
        tree = _tree(root_file, tree_name, field_names)
        arrays = tree.arrays(field_names, library="np")
    return _structured_records(arrays, field_names)


def ntuple_fields(filename, tree_name):
    """Return the branch names stored in a ROOT ntuple."""
    with uproot.open(filename) as root_file:
        return tuple(_tree(root_file, tree_name, ()).keys())


def iterate_ntuple(filename, tree_name, field_names, step_size="100 MB"):
    """Yield bounded chunks from a Geant4 ROOT ntuple."""
    path = Path(filename)
    with uproot.open(path) as root_file:
        tree = _tree(root_file, tree_name, field_names)
        for arrays in tree.iterate(
            field_names,
            step_size=step_size,
            library="np",
        ):
            yield _structured_records(arrays, field_names)


def has_ntuple(filename, tree_name):
    """Return whether a ROOT file contains the named ntuple."""
    with uproot.open(filename) as root_file:
        return tree_name in root_file
