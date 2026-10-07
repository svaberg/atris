# Prepare an Earth atmosphere simulation

**Next step:** [Plan chunks for the prepared simulation](../running-atris/plan-chunks.md).

This example prepares an Earth simulation from the supplied `simulation.psf`.
Its atmosphere has 101 layers, each 1 km thick, extending from the surface to
101 km altitude. The PSF also includes the solid interior, crust, and outer
stopping shell.

These preparation steps are independent of execution environment. Continue with
[chunk planning](../running-atris/plan-chunks.md) once the inputs are ready.

The particle inputs use the `atris-generate-macros` defaults: 121 logarithmically
spaced output-bin edges and a continuous log-uniform source over the same
energy range. The event-count settings produce 363,000 proton events and
239,580 alpha events.

## Create the run directory

From `runs/`, create and enter the run directory:

```bash
mkdir earth-nrlmsis-full
cd earth-nrlmsis-full
```

## Prepare the atmosphere

Copy the example's PSF into the run directory:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-full/simulation.psf" .
```

To use a different time or location, follow
[Download an atmosphere from NASA](../running-atris/download-nasa-atmosphere.md)
to obtain and convert a new profile instead.

Convert the PSF to the Geant4 geometry `simulation.gdml`:

```bash
atris-psf-to-gdml simulation.psf
```

## Prepare the phantom inputs

Copy and stage the example's two-phantom selection:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-full/phantoms.txt" .
atris-stage-phantoms .
```

## Prepare the particle inputs

Generate inputs with the default energy grid and particle counts. The values
are written out explicitly below, and the fixed random seed makes the generated
macros reproducible:

```bash
atris-generate-macros . \
  --particles-per-bin 3000 \
  --alpha-factor 0.66 \
  --random-seed 12345 \
  --energy-min-power 0 \
  --energy-max-power 6 \
  --energy-points 121
```

These are the `atris-generate-macros` defaults except for `--random-seed 12345`;
omitting that option generates new random seeds. With 121 output-bin edges, AtRIS
will process 363,000 proton events (`121 x 3000`) and 239,580 alpha events
(`121 x int(3000 x 0.66)`).

## Physics choices and execution

Use `FTFP_BERT_HP` and `response` output for
this example. It includes two phantoms. The prepared files now define the
simulation; no events have run yet.

Choose [local](../running-atris/run-locally.md),
[server/workstation](../running-atris/run-on-server.md), or
[HPC](../hpc.md) execution. First [prepare a chunk plan](../running-atris/plan-chunks.md);
the runner reads the phantom count from `phantoms.txt`.

Start with [a few chunks](files-through-workflow.md#6-plan-and-run-chunks),
[gather and inspect their results](../running-atris/process-results.md), and
[decide whether to continue](../running-atris/process-results.md#decide-whether-to-continue). This keeps the same
atmosphere, energy range, and particle inputs.

After a chunk completes, [gather, post-process, and plot](../running-atris/process-results.md).

Once you have processed responses, continue with the Jupyter notebook
[Fold the Earth responses with a cosmic-ray spectrum](earth-spectrum-folding.ipynb)
to calculate the proton contribution to ionization and water-phantom dose. The notebook is at
`docs/tutorials/earth-spectrum-folding.ipynb`.
[View notebook](earth-spectrum-folding.ipynb) or download
{download}`earth-spectrum-folding.ipynb <earth-spectrum-folding.ipynb>`.

## Prepared reference files

The example contains the PSF and the geometry and particle inputs generated
from it. Simulation outputs, plots, logs, and staged phantom links
are not included.

As an alternative to generating the inputs above, copy the prepared example
into a fresh run directory. Do not repeat this in a directory already used for
a simulation:

```bash
mkdir earth-nrlmsis-full
cd earth-nrlmsis-full
cp -R "$ATRIS_ROOT/examples/earth-nrlmsis-full/." .
atris-stage-phantoms .
```


**Next step:** [Plan chunks for the prepared simulation](../running-atris/plan-chunks.md).
