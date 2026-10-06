# Scatter/gather files

## Layout and plan syntax

A scattered run keeps shared inputs at its root and per-chunk output in
`chunks/`:

```text
run/
    simulation.psf
    phantoms.txt
    protons.gdml
    protons.bins
    protons.mac
    protons.chunk.mac
    alphas.gdml
    alphas.bins
    alphas.mac
    alphas.chunk.mac
    chunks.txt
    chunks/
        protons_123456_654321.log
        protons_123456_654321_h1_h1.1.csv
        protons_123456_654321_h2_h2.ion.csv
        protons_123456_654321_h2_h2.edep.csv
        ...
        protons_123456_654321.COMPLETE
```

The descriptive phantom files named in each species macro must also be staged
at the run root. A `chunks.txt` row has exactly three whitespace-separated
fields, without a header or comments:

```text
protons 123456 654321
alphas 234567 765432
```

The generated plan uses six-digit seeds in the range 31–999999. Each row's
output basename is `<species>_<seed1>_<seed2>`. Plan line numbers are one-based.
The seed fields are data read by `atris-run`; the executable does not infer
seeds from the output basename.

## Creation and extension

`atris-scatter --chunks N` creates `N` entries per species, or `2N` total,
with all proton entries followed by all alpha entries. For each species:

$$
n_{\mathrm{chunk}}=\left\lceil\frac{n_{\mathrm{requested}}}{N}\right\rceil,
\qquad n_{\mathrm{actual}}=N n_{\mathrm{chunk}}.
$$

Here $N$ is the requested chunk count per species and
$n_{\mathrm{requested}}$ is the ordinary macro's event count.

The ordinary macro must contain exactly one positive `/run/beamOn` command,
one `/atris/outputFile` command, and one `/atris/randomSeeds` command. The chunk
macro changes the event count and replaces the output and seed values with
Geant4 aliases; the ordinary macro remains unchanged. `atris-run` defines those
aliases in a temporary wrapper for each plan entry. The actual total exceeds
the requested total by fewer than `N` events when rounding is necessary.

Creation refuses an existing plan, an existing chunk macro, or a nonempty
`chunks/`. It permits an already existing empty `chunks/` directory.

`--extend N` appends `N` entries per species with new unique seed pairs. It
preserves the existing chunk macros and their event counts. The plan is
replaced atomically after writing the appended version. Active workers keep
using the plan they read at startup; newly appended entries become available
to subsequent runner invocations. Extension does not
revise the physical inputs or rerun completed entries. When changing the setup,
[account for existing outputs](../running-atris/process-results.md#decide-whether-to-continue)
before gathering old and new chunks together.

For choosing chunk size, see [Plan chunks and restarts](../running-atris/plan-chunks.md#choose-a-practical-chunk-size).

## Worker assignment and completion

Worker index `r` among `W` externally launched workers receives plan lines:

$$
\ell_j=r+1+jW,\qquad j=0,1,2,\ldots
$$

Only line numbers within the plan are selected.

Worker indices are zero-based. `--entry N` selects one one-based plan entry
instead. Each worker runs its selected incomplete entries sequentially. When
the plan length is not divisible by the worker count, some workers receive one
extra entry; execution still proceeds normally.

The runner redirects the executable's stdout and stderr to `<chunk>.log`.
It creates an empty `<chunk>.COMPLETE` marker only after the subprocess returns
success. A failed subprocess stops that worker and leaves the chunk unmarked.
On retry, unmarked chunks are rerun from the beginning; their logs and outputs
can be replaced. There is no within-chunk checkpoint.

A marker is a completion signal, not a checksum or independent output
validation. The runner skips a marked chunk even if its inputs were changed
or its outputs were removed. `--check-complete` checks markers for the entire
plan and returns `0` if all exist, `1` otherwise; it does not inspect payloads.

Deadlines are checked before starting each chunk. A running chunk is never
interrupted by `--deadline` or `--stop-before-end`. A worker stopping at the
safety window can return success while work remains; use `--check-complete`
for whole-plan completion.

Worker assignments do not use filesystem locks. Do not run overlapping worker
pools or multiple workers with the same index against a shared plan.

## Gather products and restart behaviour

`atris-gather` reads only planned chunks whose `.COMPLETE` markers exist. It
sums histogram accumulators into canonical `<species>_*.csv` files for CSV
chunks or `<species>.root` for ROOT chunks. It never averages already
normalized response tables. Incomplete chunk files are ignored; a required
histogram missing from a completed chunk is an error. CSV headers and shapes,
or ROOT histogram definitions and axes, must agree.

The first completed chunk determines the set of histogram suffixes to gather.
Every other completed chunk must provide those suffixes. Keep configuration
and phantom counts fixed throughout a plan; gather is not a comprehensive
configuration-consistency check.

| Product | Contents |
| --- | --- |
| `<species>_*.csv` or `<species>.root` | Sum of the selected completed raw response histograms. |
| `<species>.gathered-chunks.txt` | The plan triples included in the aggregate, in plan order. |
| `<species>.convergence.csv` | Ionization convergence history when at least two chunks are available. |

Primary and ionization histograms are rebuilt to compute convergence. Other
histograms can reuse an aggregate when the earlier gathered entries are an
unchanged prefix of the current completed entries and file timestamps permit
reuse; otherwise they are rebuilt. Each written file is replaced atomically,
but the whole collection of products is not one atomic transaction. Run only
one gather/post-processing writer at a time.

With no completed chunks for a species, gather skips it and does not clear old
canonical files. Likewise, a new convergence table is only written when there
are at least two chunks. Retain one consistent plan and its outputs per run
directory rather than recycling old result directories.

Gather can inspect the completed subset while workers run, provided completed
chunks remain immutable. For a final result, first verify whole-plan completion.
Gather does not merge the `interfaces` or `steps` ROOT ntuples, scale response
tables, or make plots. Those particle records remain per chunk; the canonical
ROOT file contains the gathered response histograms and their metadata rows.
Run post-processing and plotting separately for canonical response products.

## Convergence CSV

Rows are constructed in completed **plan order**, not completion-time order,
starting at two completed chunks. For `n` chunks, compare the current cumulative
ionization response with the response before the last $\lceil 0.1n\rceil$ chunks.

| Column | Meaning |
| --- | --- |
| `completed_chunks` | Number `n` of accumulated chunks. |
| `primary_events` | Accumulated in-range primary entries. |
| `comparison_chunks` | Number of final chunks added for the comparison. |
| `comparison_percent` | $100\,n_{\mathrm{comparison}}/n$. |
| `ionization_change_percent` | The percentage $\Delta$ defined below. Zero when the denominator is zero. |
| `cell_change_p50_percent`, `cell_change_p90_percent` | Percentiles of that symmetric fractional change computed per populated detector/energy cell, multiplied by 100. |
| `cell_relative_se_p50_percent`, `cell_relative_se_p90_percent` | Percentiles of estimated relative standard error across finite cells, multiplied by 100. |

For current values $a_j$ and previous values $b_j$ over the compared cells,

$$
\Delta=100\frac{\sum_j\lvert a_j-b_j\rvert}
{\sum_j(\lvert a_j\rvert+\lvert b_j\rvert)}.
$$

Changes use the volume-normalized ionization response with terminating layers
excluded. Non-finite values are replaced by zero for change calculations.
Standard errors are estimated from primary-count-weighted chunk means: for
chunk means $x_i$, primary counts $w_i$, weighted mean $\mu$, and $k$ contributing
chunks in that energy bin,

$$
\mu=\frac{\sum_i w_i x_i}{\sum_i w_i},\qquad
Q=\sum_i w_i(x_i-\mu)^2,
$$

$$
\mathrm{SE}=\sqrt{\frac{Q}{(k-1)\sum_i w_i}},\qquad
\mathrm{relative\_SE}=\frac{\mathrm{SE}}{\lvert\mu\rvert}.
$$

Undefined relative errors are excluded from percentiles. These are convergence
diagnostics for ionization, not uncertainty estimates for every output product.

Implementation: `atris_tools/scatter.py`, `run_chunks.py`, and `gather.py`.
