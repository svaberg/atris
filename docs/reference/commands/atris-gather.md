# atris-gather

Sum completed chunk histograms into canonical species outputs.

```bash
atris-gather .
atris-gather . protons
```

The optional directory comes before optional species names, so use `.` when
selecting a species in the current directory. Defaults are `protons alphas`.
The supported workflow uses these two species.

**Inputs:** `chunks.txt`, marked completed chunks, and `simulation.psf` for
ionization convergence. **Outputs:** canonical `<species>_*.csv` histograms or
`<species>.root`, `<species>.gathered-chunks.txt`, and convergence tables when
at least two chunks are available. Outputs are updated/replaced; no completed
chunks means that species is skipped, not that old canonical files are removed.

For CSV and ROOT chunks, response histograms and metadata are gathered while
interface and step ntuples remain in the chunk files. This command does not run
missing chunks, normalize response tables, or plot. See
[gather state and convergence](../chunks.md).

The progress summary reports how many chunks have completed. With at least
two completion markers, it also estimates the average completion interval
and time remaining from recent marker timestamps. This estimate reflects
the observed throughput and can change when worker availability changes.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-gather [-h] [-q | -v] [--version] [RUN_DIRECTORY] [SIMULATION ...]

Combine completed AtRIS chunk histograms into canonical aggregate CSV or ROOT output
and update ionization-convergence histories.

positional arguments:
  RUN_DIRECTORY  Scattered run directory (default: current directory).
  SIMULATION     Simulation prefixes to gather (default: protons alphas).

optional arguments:
  -h, --help     show this help message and exit
  -q, --quiet    Suppress normal progress; show warnings and errors only.
  -v, --verbose  Include detailed per-file, per-request, or per-chunk progress.
  --version      Show the AtRIS and atris-tools versions and exit.

Only chunks with .COMPLETE markers are included; partial files from failed or running
chunks are ignored. Primary and ionization histograms are rebuilt to update the
complete convergence history. Other CSV histograms reuse a validated aggregate and
add only newly completed chunks; ROOT response histograms are rebuilt together. ROOT
interface and step ntuples remain in their chunk files. This command does not run missing
chunks, scale physical response files, or make plots. To select one
species in the current directory, use an explicit dot, for example: atris-gather .
protons.
```

Implementation: `atris_tools/gather.py`.
