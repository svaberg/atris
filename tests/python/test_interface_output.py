import numpy as np
import pytest
import uproot

from atris_tools.interface_output import (
    INTERFACE_DTYPE,
    read_interface_output,
    read_root,
)

SAMPLE_RECORDS = np.array(
    [
        (2212, 2, 125, 100.0, 100.0),
        (22, 3, 45, 12.5, 100.0),
        (11, 4, 92, 1.25, 10.0),
    ],
    dtype=INTERFACE_DTYPE,
)


def write_root(path, records=SAMPLE_RECORDS):
    with uproot.recreate(path) as root_file:
        root_file.mktree(
            "interfaces",
            {
                "pdg": "int32",
                "interface_id": "int32",
                "angle_degrees": "int32",
                "kinetic_energy_MeV": "float64",
                "primary_energy_MeV": "float64",
            },
        )
        root_file["interfaces"].extend(
            {
                "pdg": records["pdg"],
                "interface_id": records["interface"],
                "angle_degrees": records["angle"],
                "kinetic_energy_MeV": records["kinetic_energy"],
                "primary_energy_MeV": records["source_energy"],
            }
        )


def test_read_root_returns_interface_records(tmp_path):
    root_path = tmp_path / "protons.root"
    write_root(root_path)

    np.testing.assert_array_equal(read_root(root_path), SAMPLE_RECORDS)


def test_read_interface_output_uses_simulation_prefix(tmp_path):
    write_root(tmp_path / "protons.root")

    records, source = read_interface_output(tmp_path / "protons")

    np.testing.assert_array_equal(records, SAMPLE_RECORDS)
    assert source.name == "protons.root"


def test_read_interface_output_requires_root_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="protons.root"):
        read_interface_output(tmp_path / "protons")


def test_read_root_requires_interface_ntuple(tmp_path):
    path = tmp_path / "protons.root"
    with uproot.recreate(path) as root_file:
        root_file.mktree("steps", {"event_id": "int32"})

    with pytest.raises(ValueError, match="does not contain the interfaces ntuple"):
        read_root(path)


def test_read_root_requires_all_interface_columns(tmp_path):
    path = tmp_path / "protons.root"
    with uproot.recreate(path) as root_file:
        root_file.mktree("interfaces", {"pdg": "int32"})

    with pytest.raises(ValueError, match="interfaces ntuple is missing columns"):
        read_root(path)
