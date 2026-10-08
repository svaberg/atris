# Energetic electrons in the Earth atmosphere

This example launches 500 primary electrons with kinetic energies of 1--100 MeV
onto the Earth model from `examples/earth-nrlmsis-full/simulation.psf`. Source
positions lie on a sphere surrounding the atmosphere, with inward cosine-law
incidence. Energies are sampled uniformly in their logarithm, not from a measured
electron spectrum. The output records ionizing and total energy deposition;
no phantom response tables are used.

Activate the installed AtRIS Python environment and source `setup_atris.sh` as
described in [the installation guide](../../INSTALL.md). Start inside `runs/`
in the recommended layout, beside the `atris/` checkout:

```bash
mkdir earth-electrons
cd earth-electrons
cp ../../atris/examples/earth-electrons/electrons.mac .
cp ../../atris/examples/earth-electrons/electrons.bins .
cp ../../atris/examples/earth-nrlmsis-full/simulation.psf .
atris-psf-to-gdml simulation.psf --output electrons.gdml
```

The macro comments explain each setting. `electrons.bins` contains 20
logarithmically spaced kinetic-energy bins between 1 and 100 MeV. The 1 m
secondary-production range cut in the macro controls production of secondaries;
it does not terminate particles at a fixed energy.

Run two independently seeded chunks, each with 250 primary electrons:

```bash
atris-scatter . electrons --chunks 2 --random-seed 42
atris-run .
atris-gather . electrons
atris-postprocess . electrons
atris-plot . electrons
```

The explicit `electrons` argument selects the macro/output stem instead of the
usual `protons` and `alphas`. `atris-run` reads that selection from `chunks.txt`.
Rerunning it skips completed chunks.

Each completed chunk has a ROOT file and a log in `chunks/`. Gathering produces
`electrons.root` and `electrons.convergence.csv`. Post-processing writes
`electrons.ioni` and `electrons.edep`, normalized per primary in each energy bin
and per layer volume. Plotting writes `electrons.inputs.png`, `electrons.png`,
`electrons.convergence.png`, and `simulation.psf.png`. At 500 primaries these are
quick-look results; increase `/run/beamOn` in a new run to improve sampling.
