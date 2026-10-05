# Prepare the simulation

**Next step:** [Plan chunks and restarts](plan-chunks.md).

Prepare the planetary model, optional phantom responses, and particle sampling
before setting up the job. The same inputs can then run locally, on a server,
or on an HPC system. AtRIS and its Python tools must already be
[installed](installation.md).

For a worked example with every intermediate file explained, use
[Follow the files through an AtRIS run](../tutorials/files-through-workflow.md).
This guide describes the choices and commands for preparing your own simulation.

```{toctree}
:hidden:

download-nasa-atmosphere
```

## Start with your PSF

`simulation.psf` describes the planetary layers and their materials. Use an
existing model, [build one in the exoplanet notebook](../tutorials/exoplanet-psf.ipynb),
or [convert an Earth atmosphere from NASA](download-nasa-atmosphere.md).
Inspect the layer boundaries, units, density, and composition before generating
other inputs; the [PSF reference](../reference/inputs.md#planet-specification-format-psf)
defines the format.

The recommended layout places `runs/` beside the AtRIS directory. From `runs/`,
or another directory where you keep simulations, create and enter a new run
directory. Replace `/path/to/model` with the directory containing your PSF:

```bash
mkdir simulation-run
cd simulation-run
cp /path/to/model/simulation.psf .
```

Use an unused directory name and keep the filename `simulation.psf`. If you
already created the model in its own run directory, work there instead of
copying it again. Run the remaining commands inside that directory.

## Convert the geometry

```bash
atris-psf-to-gdml simulation.psf
```

This creates `simulation.gdml`, the geometry and material description read by
Geant4. Keep the PSF: post-processing also uses its layer geometry.

## Optionally select phantoms

Skip this step if you only need atmospheric transport and ionizing energy
deposition. For phantom responses, create `phantoms.txt` in the run directory,
listing the selected table stems and their masses and areas. Choose the
material, detector, and shielding appropriate to your observable from the
[phantom library](../reference/phantom-library.md). The
[selection-file reference](../reference/inputs.md#phantom-selection) gives the
row format and ID convention.

Once that file is ready, stage its tables:

```bash
atris-stage-phantoms . --copy
```

This copies the selected named tables into the run directory and creates the
numbered links expected by AtRIS. Keeping the targets local lets you transfer
the whole directory to another machine. The runner reads the selection from
`phantoms.txt`.

The phantom tables define the response accumulated during particle transport.
Changing them later does not change the response already recorded in the
histograms, so select them as part of the physical setup before preparing the
particle sampling.

## Prepare particle inputs

The standard macro generator prepares separate proton and alpha simulations.
Choose the energy range, number of energy points, and event counts for your
calculation. For example, the following explicitly sets the generator's
standard sampling values and fixes the seed used to generate macros:

```bash
atris-generate-macros . \
  --energy-min-power 0 \
  --energy-max-power 6 \
  --energy-points 121 \
  --particles-per-bin 3000 \
  --alpha-factor 0.66 \
  --physics-list FTFP_BERT_HP \
  --output-mode response \
  --random-seed 12345
```

Adapt these values to the particles and energies relevant to your study.
The energy powers specify proton kinetic energies in MeV; alpha energies are
four times the proton values. These are total energies per particle, not
energies per nucleon. Event counts control statistical sampling, not physical
source intensity. The [energy-grid and event-count conventions](../reference/inputs.md#energy-bins-and-macros)
explain exactly how the options determine the generated inputs.

The command creates `.gdml`, `.mac`, and `.bins` files for each species. It
refuses to overwrite existing species inputs. Check the generated macros if
your study requires a different source position or angular distribution; the
[macro-generator reference](../reference/commands/atris-generate-macros.md)
describes the supported options.

Additional macro batches can sample more particles for the same physical setup.
For example, batches with different event counts and independent random seeds
can contribute to the same result when their geometry, physics, phantom
responses, source distribution, and histogram bins agree. Combine their raw
histograms and [normalize by the combined primary counts](../background/normalization-and-uncertainty.md#gather-raw-sums-before-normalization).
For more sampling with the existing macros, use [chunk extension](plan-chunks.md#extend-a-run).

## Record physics and output choices

Choose a [Geant4 physics list](../background/physics-lists.md) and an
[output mode](../reference/executable.md#output-modes) when generating the
macros. The launch guides use `FTFP_BERT_HP` and `response`. During the current
command-line transition, supply the same choices to `atris-run`; AtRIS rejects
a mismatch. These choices belong to the physical calculation and remain in
the generated macro files.

## Check the prepared inputs

With the plotting extra installed, inspect the model and source before running:

```bash
atris-plot .
```

Review the species input plots and, if selected, the phantom input plots.
Keep the following files together:

| Input | Purpose |
| --- | --- |
| `simulation.psf` and `simulation.gdml` | Planetary model and converted geometry |
| Species `.gdml`, `.mac`, and `.bins` | Geometry, source sampling, total events, and energy axes |
| Optional `phantoms.txt` and staged tables | Phantom selection, response coefficients, and normalization metadata |

The physical inputs are ready. Chunk planning divides the requested events
into restartable batches without changing this model. Run a few of those batches,
gather and inspect their results, and decide whether to continue the full plan.

**Next step:** [Plan chunks and restarts](plan-chunks.md).
