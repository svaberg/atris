# atris-postprocess

Normalize canonical raw histograms into response tables.

```bash
atris-postprocess .
```

The directory defaults to the current directory. Both `protons` and `alphas`
are attempted, and a species without its primary histogram is skipped. There
is no positional species filter.

**Inputs:** canonical histogram CSV or ROOT files, `simulation.psf`, and phantom
mass/area metadata from `phantoms.txt` when phantom products are present.
**Outputs:** `.ioni`, `.edep` when the raw total-deposition tally is present,
and `.<stem>.dose`, `.<stem>.equi`, and `.<stem>.rates`, replacing existing
processed files.
Available input/output consistency checks produce warnings.

Phantom mass and area are post-processing scale factors only. They are not
read by the C++ executable and do not affect particle transport or raw
histogram accumulation. Dose and equivalent-dose products use both mass and
area; counting-rate products use area but not mass.

The output is normalized per simulated primary energy bin; it does not include
source-flux folding or conversion into physical rates. See
[processed response tables](../outputs.md#processed-response-tables) for units,
formulas, geometry assumptions, and empty-bin handling.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-postprocess [-h] [-q | -v] [--version] [RUN_DIRECTORY]

Scale canonical AtRIS CSV or ROOT histograms into altitude- and
energy-dependent atmospheric energy-deposition and phantom response tables.

positional arguments:
  RUN_DIRECTORY  Run directory containing canonical response output (default:
                 current directory).

options:
  -h, --help     show this help message and exit
  -q, --quiet    Suppress normal progress; show warnings and errors only.
  -v, --verbose  Include detailed per-file, per-request, or per-chunk
                 progress.
  --version      Show the AtRIS and atris-tools versions and exit.

The command processes the protons and alphas prefixes when their primary
histogram files are present. It reads simulation.psf and, for phantom
responses, phantoms.txt; it writes .ioni, .edep when total-deposition input is
present, and stem-named dose, equi, and rates files, replacing existing
processed files. Missing species are skipped. This command does not gather chunk
histograms, run simulations, or make plots.
```

Implementation: `atris_tools/postprocess.py`.
