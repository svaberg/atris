"""Exercise the electron example through transport and response processing."""

from pathlib import Path
import shutil

import numpy as np
import pytest

from atris_tools.gather import gather_simulation, read_chunk_plan
from atris_tools.input_plotting import plot_inputs
from atris_tools.plotting import plot_convergence, plot_run
from atris_tools.postprocess import process_run
from atris_tools.psf2gdml import psf2gdml
from atris_tools.response_histograms import (
    IONIZATION_HISTOGRAM,
    PRIMARY_HISTOGRAM,
    TOTAL_DEPOSITION_HISTOGRAM,
    ResponseHistogramReader,
)
from atris_tools.run_chunks import run_chunks
from atris_tools.scatter import scatter

EXAMPLES = Path(__file__).parents[2] / "examples"


@pytest.mark.regression
@pytest.mark.parametrize("output_format", ("root", "csv"))
def test_earth_electrons_end_to_end(tmp_path, monkeypatch, output_format):
    assert shutil.which("AtRIS"), "Load the Geant4 runtime and put AtRIS on PATH."
    monkeypatch.setenv("G4FORCENUMBEROFTHREADS", "2")
    monkeypatch.chdir(tmp_path)
    shutil.copyfile(
        EXAMPLES / "earth-nrlmsis-full" / "simulation.psf",
        "simulation.psf",
    )
    shutil.copyfile(EXAMPLES / "earth-electrons" / "electrons.bins", "electrons.bins")
    macro = (EXAMPLES / "earth-electrons" / "electrons.mac").read_text()
    Path("electrons.mac").write_text(
        macro.replace(
            "/atris/outputFormat root", "/atris/outputFormat " + output_format
        )
    )
    psf2gdml("simulation.psf", "electrons.gdml")

    scatter(tmp_path, chunks=2, random_seed=42, simulations=("electrons",))
    assert run_chunks(tmp_path) == 2
    assert run_chunks(tmp_path) == 0
    entries = read_chunk_plan(tmp_path)
    assert gather_simulation(tmp_path, entries, "electrons") == 2

    with ResponseHistogramReader("electrons") as histograms:
        primary = histograms.values(PRIMARY_HISTOGRAM)
        ionization = histograms.values(IONIZATION_HISTOGRAM)
        deposition = histograms.values(TOTAL_DEPOSITION_HISTOGRAM)
        assert primary[1:-1].sum() == 500
        assert primary[1:-1].min() > 0
        assert primary[[0, -1]].sum() == 0
        # Geant4 CSV stores these edges with six significant digits.
        np.testing.assert_allclose(
            histograms.axes(PRIMARY_HISTOGRAM)[0],
            np.loadtxt("electrons.bins"),
            rtol=1e-5,
        )
        assert np.isfinite(ionization).all()
        assert ionization.sum() > 0
        assert np.all(deposition >= ionization - 1e-10)
        assert histograms.phantom_stems() == set()

    process_run("electrons")
    ionization_table = np.loadtxt("electrons.ioni")
    deposition_table = np.loadtxt("electrons.edep")
    assert ionization_table.shape == deposition_table.shape == (102, 22)
    assert np.isfinite(ionization_table).all()
    assert np.isfinite(deposition_table).all()

    inputs, input_errors = plot_inputs(("electrons",))
    results, result_errors = plot_run("electrons")
    convergence = plot_convergence("electrons")
    assert input_errors == result_errors == []
    assert set(inputs) == {"electrons.inputs.png", "simulation.psf.png"}
    assert results == ["electrons.png"]
    for filename in inputs + results + [convergence]:
        assert Path(filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
