from io import StringIO

import numpy as np
import pytest
import uproot

from atris_tools.dump import dump_ntuple
from atris_tools.interface_output import ROOT_FIELDS
from atris_tools.step_output import STEP_FIELDS


def write_ntuple(path, name, fields, row):
    columns = {field: np.asarray([value]) for field, value in zip(fields, row)}
    branch_types = {
        field: "string" if values.dtype.kind in "SU" else values.dtype
        for field, values in columns.items()
    }
    with uproot.recreate(path) as root_file:
        root_file.mktree(name, branch_types)
        root_file[name].extend(columns)


def test_dumps_interface_ntuple_as_csv(tmp_path):
    path = tmp_path / "protons.root"
    write_ntuple(
        path,
        "interfaces",
        ROOT_FIELDS,
        (2212, 2, 90, 10.0, 100.0),
    )
    output = StringIO()

    dump_ntuple(path, "interfaces", output)

    assert output.getvalue().splitlines() == [
        ",".join(ROOT_FIELDS),
        "2212,2,90,10.0,100.0",
    ]


def test_dumps_step_ntuple_as_csv(tmp_path):
    path = tmp_path / "protons.root"
    row = [0] * 6 + [0.0] * 13 + ["primary", "Transportation"]
    row[0] = 4
    row[1] = 7
    row[4] = 2212
    row[13] = 25.0
    write_ntuple(path, "steps", STEP_FIELDS, row)
    output = StringIO()

    dump_ntuple(path, "steps", output)

    lines = output.getvalue().splitlines()
    assert lines[0] == ",".join(STEP_FIELDS)
    assert lines[1].split(",")[:5] == ["4", "7", "0", "0", "2212"]
    assert lines[1].endswith(",primary,Transportation")


def test_dump_failure_writes_no_csv_header(tmp_path):
    output = StringIO()

    with pytest.raises(FileNotFoundError):
        dump_ntuple(tmp_path / "missing.root", "interfaces", output)

    assert output.getvalue() == ""
