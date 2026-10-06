# Process and inspect results

**Previous step:** [Run the simulation](run-simulation.md).

Work in the run directory containing the prepared inputs and chunk outputs.
These commands apply to local, server, and HPC runs. Use them after your first
few chunks, before deciding whether to continue the full run. Repeat them as
more chunks finish; they also work while other chunks are running.

## Gather completed chunks

```bash
atris-gather .
```

Gathering includes only planned chunks with a `.COMPLETE` marker and ignores
unfinished chunks. It combines their raw histograms into species CSVs or a
species ROOT file at the run root, matching the chunks' output mode. Run one
gather process at a time for that directory, and let it finish before
post-processing the aggregate.

`atris-run . --check-complete` tells you whether the entire plan has finished.
A successful completion check is not required to inspect the completed subset.

## Normalize and plot

After gathering, run these commands in order:

```bash
atris-postprocess .
atris-plot .
```

Post-processing needs `simulation.psf`, the species inputs, and optional
`phantoms.txt` alongside the gathered histograms. It produces ionizing and
total energy-deposition response tables (`.ioni` and `.edep`) for each
available species and, when phantoms are selected, `.<stem>.dose`,
`.<stem>.equi`, and `.<stem>.rates` tables. Raw output from older AtRIS versions
has no `h2.edep` tally;
it remains processable but produces only `.ioni` for atmospheric deposition.

Plotting creates species result images such as `protons.png` and `alphas.png`,
plus phantom result images when applicable. It also plots available model,
source, and phantom inputs. It does not gather or normalize data itself.
For a complete worked set of filenames and input/output tables, see the
[workflow tutorial](../tutorials/files-through-workflow.md#8-process-response-tables-and-plots).

## Interpret and update the results

The processed tables describe responses per simulated primary, resolved by
primary energy. They are not physical rates until an appropriate incident
spectrum and intensity are applied. See
[normalization and uncertainty](../background/normalization-and-uncertainty.md)
for interpretation and [Output files](../reference/outputs.md) for column
definitions, units, and formulas.

For a worked continuation of the Earth example, use the Jupyter notebook
[Fold the Earth responses with a cosmic-ray spectrum](../tutorials/earth-spectrum-folding.ipynb)
at `docs/tutorials/earth-spectrum-folding.ipynb`. It uses protons and one water
phantom to work through ionization and absorbed dose rates for an incident spectrum.
[View notebook](../tutorials/earth-spectrum-folding.ipynb) or download
{download}`earth-spectrum-folding.ipynb <../tutorials/earth-spectrum-folding.ipynb>`.

Unsampled energy bins have no response estimate and may contain undefined
values. Inspect the sampling before interpreting the plots. The gathered
`.convergence.csv` files describe ionization convergence across completed
chunks; their [definitions and limits](../reference/chunks.md#convergence-csv)
are given in Reference.

As more chunks finish, repeat `atris-gather`, `atris-postprocess`, and
`atris-plot` in that order. This updates the aggregate, response tables, and
plots to include the newly completed work. Retain the chunk outputs, plan,
and completion markers so gathering and resumption remain possible.

## Decide whether to continue

Review the first plots and logs before launching the remaining plan:

- **Inputs:** do the atmospheric profiles, composition, source energies, and
  optional phantom curves match the model you intended?
- **Responses:** are the expected species and phantom products present, and do
  their altitude and energy axes make sense? Distinguish unsampled bins from
  unexpected missing files, input-mismatch warnings, or failed chunks.
- **Cost:** does the measured chunk runtime and output size make the remaining
  calculation practical? Include initialization and writing in that timing.

If the setup looks right, [continue the existing plan](run-simulation.md#continue-the-run).
The initial chunks already contribute to the calculation, and the runner skips
them when it resumes. More chunks fill out the sampling and improve the statistics.

The first results may suggest changes to the setup before continuing. You can
revise it in the same directory or use another directory if you want to retain
the earlier run. Changing inputs does not automatically invalidate old chunk
outputs, completion markers, or gathered results; those still represent the
earlier setup. Account for that when rerunning and gathering so incompatible
results are not combined.

Completing a plan and reaching adequate statistics are separate decisions.
Continue inspecting the accumulating results and assess convergence for the
quantities you need.

## Need more statistics?

[Extend the chunk plan](plan-chunks.md#extend-a-run) to add more samples.
Active runners finish their existing assignments; subsequent invocations pick
up the added chunks. Gather and inspect each new completed batch. Extension adds sampling to the existing setup; for changes to
the setup, see [the considerations above](#decide-whether-to-continue).

For submitting processing through Slurm, see
[Process results in a Slurm job](../hpc.md#process-results-in-a-slurm-job).

**Previous step:** [Run the simulation](run-simulation.md).
