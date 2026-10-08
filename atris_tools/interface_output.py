"""Read particle-interface records from AtRIS ROOT output."""

from pathlib import Path

import numpy as np

from .root_output import read_ntuple

FIELD_NAMES = (
    "pdg",
    "interface",
    "angle",
    "kinetic_energy",
    "source_energy",
)
INTERFACE_DTYPE = np.dtype(
    [
        ("pdg", np.int32),
        ("interface", np.int32),
        ("angle", np.int32),
        ("kinetic_energy", np.float64),
        ("source_energy", np.float64),
    ]
)
ROOT_FIELDS = (
    "pdg",
    "interface_id",
    "angle_degrees",
    "kinetic_energy_MeV",
    "primary_energy_MeV",
)


def read_root(filename):
    """Read interface records from one AtRIS mode-0 or mode-1 ROOT file."""
    root_records = read_ntuple(filename, "interfaces", ROOT_FIELDS)
    records = np.empty(root_records.size, dtype=INTERFACE_DTYPE)
    for target, source in zip(FIELD_NAMES, ROOT_FIELDS):
        records[target] = root_records[source]
    return records


def read_interface_output(prefix):
    """Read the ROOT interface output belonging to a simulation prefix."""
    root_path = Path(str(prefix) + ".root")
    if not root_path.is_file():
        raise FileNotFoundError("No interface output found in %s" % root_path)
    return read_root(root_path), root_path
