# atris-postprocess

Normalize canonical raw histograms into response tables.

```bash
atris-postprocess .
atris-postprocess . electrons
```

The directory defaults to the current directory. By default, both `protons`
and `alphas` are attempted. List other simulation filename stems after the
directory to select them instead. A simulation without its primary histogram
is skipped.

**Inputs:** canonical histogram CSV or ROOT files, `simulation.psf`, and phantom
mass/area metadata from `phantoms.txt` when phantom products are present.
**Outputs:** `.ioni`, `.edep` when the raw total-deposition tally is present,
and one `.<stem>.<response>` file per configured response. The standard `dos`
response retains the established `.<stem>.dose` filename. Existing processed
files are replaced.
Available input/output consistency checks produce warnings.

Phantom mass and area are post-processing scale factors only. They are not
read by the C++ executable and do not affect particle transport or raw
histogram accumulation. Every phantom product uses area; each response's
explicit `scaleByInversePhantomMass` setting determines whether mass is also
used.

The output is normalized per simulated primary energy bin; it does not include
source-flux folding or conversion into physical rates. See
[processed response tables](../outputs.md#processed-response-tables) for units,
formulas, geometry assumptions, and empty-bin handling.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-postprocess [-h] [-q | -v] [--version]
                         [RUN_DIRECTORY] [SIMULATION ...]

Scale canonical AtRIS CSV or ROOT histograms into altitude- and
energy-dependent atmospheric energy-deposition and phantom response tables.

positional arguments:
  RUN_DIRECTORY  Run directory containing canonical response output (default:
                 current directory).
  SIMULATION     Simulation prefixes to process (default: protons alphas).

options:
  -h, --help     show this help message and exit
  -q, --quiet    Suppress normal progress; show warnings and errors only.
  -v, --verbose  Include detailed per-file, per-request, or per-chunk
                 progress.
  --version      Show the AtRIS and atris-tools versions and exit.

The command processes the selected simulation prefixes when their primary
histogram files are present. It reads simulation.psf and, for phantom
responses, phantoms.txt; it writes .ioni, .edep when total-deposition input is
present, and one stem- and response-named file per phantom response, replacing
existing processed files. Missing species are skipped. This command does not
gather chunk histograms, run simulations, or make plots.
```

Implementation: `atris_tools/postprocess.py`.
