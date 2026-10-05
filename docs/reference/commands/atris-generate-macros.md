# atris-generate-macros

Generate proton and alpha simulation inputs in a prepared run directory.

**Inputs:** `simulation.psf` and `simulation.gdml`.
**Outputs:** `protons.mac`, `protons.bins`, `protons.gdml`, and the corresponding
three `alphas` files. If any destination already exists, generation is refused.

```bash
atris-generate-macros . --particles-per-bin 100 --energy-points 10 --random-seed 42
```

The directory defaults to `.`. Default settings are physics list
`FTFP_BERT_HP`, 3000 proton histories per energy point, alpha factor 0.66, and
121 logarithmic points from 1 to 1e6 MeV for protons. Alpha energies are four
times those values. The alpha histories per point are truncated to an integer
before multiplication by the point count. See
[energy bins and macros](../inputs.md#energy-bins-and-macros) for the exact
event-count convention. This command does not read `.spec` files.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-generate-macros [-h] [--particles-per-bin COUNT] [--alpha-factor FACTOR]
                             [--random-seed SEED] [--energy-min-power POWER]
                             [--energy-max-power POWER] [--energy-points COUNT]
                             [--physics-list NAME] [-q | -v] [--version]
                             [RUN_DIRECTORY]

Generate the proton and alpha macros, energy grids, and geometry copies needed to run AtRIS.

positional arguments:
  RUN_DIRECTORY         Prepared run directory (default: current directory).

options:
  -h, --help            show this help message and exit
  --particles-per-bin COUNT
                        Number of proton histories per energy point (default: 3000).
  --alpha-factor FACTOR
                        Alpha histories per energy point as a fraction of the proton count; the
                        result is truncated to an integer (default: 0.66).
  --random-seed SEED    Seed for reproducible Geant4 seed pairs (default: random).
  --energy-min-power POWER
                        Base-10 exponent of the minimum proton energy in MeV (default: 0, or 1
                        MeV).
  --energy-max-power POWER
                        Base-10 exponent of the maximum proton energy in MeV (default: 6, or 1
                        TeV).
  --energy-points COUNT
                        Number of logarithmically spaced energy points, including both endpoints
                        (default: 121).
  --physics-list NAME   Geant4 reference physics list recorded in both macros (default:
                        FTFP_BERT_HP).
  -q, --quiet           Suppress normal progress; show warnings and errors only.
  -v, --verbose         Include detailed per-file, per-request, or per-chunk progress.
  --version             Show the AtRIS and atris-tools versions and exit.

RUN_DIRECTORY must already contain simulation.psf and simulation.gdml. This command does not run
AtRIS or stage phantom responses. It writes protons/alphas .mac, .bins, and .gdml files and
refuses to overwrite any of them. The proton event count is PARTICLES_PER_BIN multiplied by
ENERGY_POINTS; the alpha count uses ALPHA_FACTOR per energy point. Alpha energies are four times
the corresponding proton grid values.
```

Implementation: `atris_tools/atrismacrogen.py`.
