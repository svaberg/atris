# Running AtRIS on an HPC system

**Previous step:** [Prepare the chunk plan](running-atris/plan-chunks.md).

**Next step:** [Process the completed results](running-atris/process-results.md).

Start with a [prepared simulation](running-atris/prepare-simulation.md) and a
[chunk plan](running-atris/plan-chunks.md). The physics list and output mode
chosen during preparation are stored in the species macros.

This guide runs any prepared AtRIS simulation through a scheduler. The Slurm
templates in `examples/slurm/` specify resources and worker launches; they do
not select a planet, atmosphere, particle spectrum, or phantom configuration.

## Run a few chunks first

Start in the prepared run directory with the AtRIS and Geant4 environment
loaded. Request a small interactive allocation to run selected chunks on a
compute node. For example:

```bash
salloc --nodes=1 --ntasks=1 --cpus-per-task=4 --time=00:30:00
```

Add the account, partition, memory, and other resource settings required by
your cluster. Four cores and thirty minutes are example requests; allow enough
time for a whole chunk to initialize, run, and write its outputs. Wait until
Slurm grants the allocation before continuing.

Inside the allocated shell, launch one chunk through `srun`:

```bash
export G4FORCENUMBEROFTHREADS="$SLURM_CPUS_PER_TASK"
srun --ntasks=1 --cpus-per-task="$SLURM_CPUS_PER_TASK" --cpu-bind=cores \
    atris-run . --entry 1
```

`--entry` is a one-based line of `chunks.txt`. Repeat with selected entries
covering the other particle species. Each command exits after that chunk;
it does not start the rest of the plan. Run transport through `srun`, not
directly on the login node.

Gather and process the completed subset within the allocation:

```bash
srun --ntasks=1 --cpus-per-task=1 atris-gather .
srun --ntasks=1 --cpus-per-task=1 atris-postprocess .
srun --ntasks=1 --cpus-per-task=1 atris-plot .
```

Run these commands in order after the selected chunks finish. Once processing
has finished, leave the allocated shell with `exit` to release the resources.
Inspect the resulting PNGs and logs and
[decide whether to continue](running-atris/process-results.md#decide-whether-to-continue).
The unfinished plan is expected at this stage; do not require a whole-plan
completion check before this inspection.

## Submit a prepared simulation with Slurm

After deciding to continue, use the worker-pool script below to run the remaining
plan. It retains and skips the chunks already completed. If you revise the
setup first, [check which existing outputs still apply](running-atris/process-results.md#decide-whether-to-continue)
before submitting.

Work on the login node in the prepared run directory, with the AtRIS and
Geant4 environment loaded. Copy the submission template:

```bash
cp "$ATRIS_ROOT/examples/slurm/run-atris.slurm.sh" .
```

The complete simulation script is shown below. Edit your copy before submitting it.

```{literalinclude} ../examples/slurm/run-atris.slurm.sh
:language: bash
:caption: examples/slurm/run-atris.slurm.sh
```

### Resource request

The `#SBATCH` lines tell Slurm what to allocate. In this example:

| Setting | What it requests |
| --- | --- |
| `--nodes=5` | Five compute nodes |
| `--ntasks=20` | Twenty AtRIS workers in total |
| `--ntasks-per-node=4` | Four workers on each node |
| `--cpus-per-task=20` | Twenty CPU cores for each worker |
| `--hint=nomultithread` | Placement on physical cores rather than additional hardware threads |
| `--time=08:00:00` | An eight-hour allocation |
| `--export=ALL` | Pass the submission environment to the job |
| `--output` and `--error` | Log files under `chunks/`, with `%j` replaced by the job ID |

This uses 80 cores per node: four workers, each running a multithreaded AtRIS
process on 20 cores. Adapt these numbers to your cluster and measured run
performance. Add the account, partition, QoS, and memory request required by
your site. The prepared chunk plan supplies the `chunks/` directory used for logs.

Each worker needs enough memory for its own AtRIS process. Measure both memory
use and completed chunks per node-hour when choosing workers and cores per
worker. Increasing the thread count of one process does not necessarily
increase the total work completed on a node.

### Environment and worker launch

`set -eu` and `set -o pipefail` make command failures and missing variables stop
the script. The `ATRIS_ROOT` check catches a missing AtRIS setup before launch.
`cd` enters the directory from which you submitted the job, where the prepared
inputs and `chunks.txt` are located.

`G4FORCENUMBEROFTHREADS` gives each AtRIS process the number of threads requested
by `--cpus-per-task`. The `srun` command launches the 20 workers and binds them
to their allocated cores. Inside each task, `bash -c` reads that task's Slurm
variables and passes them to `atris-run`:

| Runner argument | Value supplied by Slurm | Purpose |
| --- | --- | --- |
| `--worker-index` | `SLURM_PROCID` | Identifies this worker, starting at zero |
| `--worker-count` | `SLURM_NTASKS` | Gives the total number of workers |
| `--deadline` | `SLURM_JOB_END_TIME` | Gives the allocation's end time as Unix seconds |
| `--stop-before-end` | `ATRIS_STOP_BEFORE_END` | Stops starting new chunks before that deadline |

Each worker runs its assigned chunks sequentially. With 20 workers, worker 0
receives lines 1, 21, 41, and so on from `chunks.txt`; worker 1 receives lines
2, 22, 42, and so on. Their assignments do not overlap. Each chunk starts a new
AtRIS process; `srun` remains active until the workers exit.

AtRIS reads the physics list and output mode from each prepared species macro;
the scheduler script does not repeat those settings.

### Wall time and completion

`ATRIS_STOP_BEFORE_END` defaults to 1,800 seconds, or 30 minutes. During that
final interval, workers finish their active chunks but start no new ones.
Set this interval longer than a measured slow chunk plus time to write its
outputs. Initialization and final writing include serial work: short chunks
repeat that overhead frequently, while long chunks leave more work to repeat
after an interruption. See [chunk planning](running-atris/plan-chunks.md#choose-a-practical-chunk-size).

`--kill-on-bad-exit=0` lets the other workers finish if one fails. The job still
reports the failure. If the workers exit successfully, the final
`atris-run --check-complete` checks whether the whole plan is finished. It
returns failure if chunks remain, including after a planned safety stop. This
allows a dependent final-processing job to distinguish completion from a run
that needs another allocation.

For this Slurm layout, choose a chunk count per species divisible by the node
count. This convention applies to this layout, not to AtRIS runs in general.
Keep the existing plan when resubmitting: completed chunks will be skipped.

### Submit and monitor

Submit from the run directory:

```bash
simulation_submission=$(sbatch --parsable run-atris.slurm.sh)
simulation_job=${simulation_submission%%;*}
echo "$simulation_job"
```

The second command removes an optional cluster suffix from the job ID.
Submission starts the scheduling process. Monitor the job and keep inspecting
completed results as it runs. To follow its state and logs:

```bash
squeue -j "$simulation_job"
tail -f "chunks/slurm-${simulation_job}.out"
```

Ctrl+C stops `tail`, not the job. To compare completed and planned chunks:

```bash
find chunks -maxdepth 1 -name '*.COMPLETE' -type f | wc -l
wc -l chunks.txt
```

After the allocation exits, verify completion:

```bash
atris-run --check-complete
```

If entries remain, inspect the logs and resubmit the same script after the
previous allocation has exited. Completed chunks are skipped. Do not overlap
two allocations for the same plan. The script returns failure while entries
remain, including when its safety window stopped further work.

You can [process and inspect completed chunks](running-atris/process-results.md)
while the allocation continues; the completion check is only needed to confirm
that the entire plan has finished. The section below shows how to
[process results in a Slurm job](#process-results-in-a-slurm-job).

## Process results in a Slurm job

The [gathering, normalization, and plotting commands](running-atris/process-results.md)
can run in a separate Slurm allocation. The supplied template checks that the entire plan has
finished before processing, so it is intended for final results. For an interim
inspection, run those commands on completed chunks using an interactive
allocation or a separate job without that completion check.

To use the final-results template, copy it into the run directory:

```bash
cp "$ATRIS_ROOT/examples/slurm/gather-atris.slurm.sh" .
```

The complete processing script is:

```{literalinclude} ../examples/slurm/gather-atris.slurm.sh
:language: bash
:caption: examples/slurm/gather-atris.slurm.sh
```

This requests one task on one node, with one CPU, 8 GB of memory, and one hour.
Gathering writes shared aggregate files, so run only one gathering process at a
time for a run directory. Adjust the memory and wall time to the output size,
and add your cluster's account and partition settings.

After entering the submission directory, the script runs four commands in order:

1. `atris-run --check-complete` requires the entire plan to be complete for this
   final-processing job. Remove this line in a copy used to inspect completed
   chunks while the simulation continues.
2. `atris-gather` combines the completed chunks' raw histograms.
3. `atris-postprocess` normalizes the gathered results into response tables.
4. `MPLBACKEND=Agg atris-plot` creates plots without requiring a graphical display.

Because the script uses `set -e`, a failed command stops the job before the
next step. Its `#SBATCH` log paths use `%j` to include the processing job ID.

Submit from the run directory:

```bash
gather_submission=$(sbatch --parsable gather-atris.slurm.sh)
gather_job=${gather_submission%%;*}
echo "$gather_job"
```

The template checks completeness, then runs `atris-gather`, `atris-postprocess`,
and `atris-plot` as one task. Logs are written to `chunks/gather-<job-id>.out`
and `.err`. Wait for the job to finish successfully before inspecting results
or extending the simulation.

When the active simulation allocation is expected to finish the entire plan,
you can queue processing after its success instead:

```bash
gather_submission=$(sbatch --parsable \
  --dependency="afterok:${simulation_job}" gather-atris.slurm.sh)
```

Here `simulation_job` is the job ID saved at submission. The simulation script
returns failure if chunks remain, so the dependent job cannot process partial
results. If the simulation needs resubmission, submit processing after the
final successful allocation instead.

## Extend an unconverged run

[Extend the chunk plan](running-atris/plan-chunks.md#extend-a-run) to add more
samples. This can be done while the current allocation runs; its workers finish
their existing assignments. After that allocation exits, submit the same
simulation script again to pick up the added chunks and any other unfinished
entries. Choose the extension count with this page's node-count convention in
mind. If final processing was submitted with a dependency, attach it to the new
simulation job ID.

## Failure and recovery reference

| Event | Preserved work | Action |
| --- | --- | --- |
| One chunk fails | Earlier `COMPLETE` chunks | Inspect its `.log`; resubmit |
| One worker fails | Completed work from all workers | Inspect `sacct`; resubmit |
| Safety window starts | All completed chunks | Resubmit if the plan is incomplete |
| Hard wall-time kill | All `COMPLETE` chunks | Resubmit; active chunks restart |
| All markers exist | The complete simulation | Run final gather |

Partial output files from failed chunks are ignored because they have no
`COMPLETE` marker. A later attempt replaces them. If a site-specific wrapper
uses node-local scratch, copy every output and log back before creating the
marker.

## Other schedulers

The runner also accepts explicit worker coordinates and an absolute deadline:

```bash
export G4FORCENUMBEROFTHREADS=<cores-per-worker>
atris-run \
    --worker-index <zero-based-rank> \
    --worker-count <total-workers> \
    --deadline <allocation-end-unix-time> \
    --stop-before-end <safety-window-seconds>
```

Launch one such process per worker slot, give every process a unique rank, and
bind each to its own cores. All workers and the final gather must see the same
run directory. Do not launch overlapping worker pools for one run.

## Shared-filesystem sizing

Every worker reads common inputs but writes a unique set of histogram files.
Small chunks multiply fixed-size output files and gathering work.

In one development run, a 2,420-entry full-atmosphere plan used 300 events per
proton chunk. Completed chunks took roughly two minutes with four threads and
produced about 20 MB across ten CSV files each. If all entries were similar,
the complete plan would produce approximately 49 GB of chunk CSVs. This is not
a cluster benchmark; it shows why chunk size and worker concurrency must be
chosen with storage capacity in mind.

If metadata or write load becomes significant, use larger chunks, run fewer
workers per node, or stage through unique node-local directories. Keep final
chunk outputs and `COMPLETE` markers on storage visible to gather.

After execution, use [the shared results-processing guide](running-atris/process-results.md).


**Previous step:** [Prepare the chunk plan](running-atris/plan-chunks.md).

**Next step:** [Process the completed results](running-atris/process-results.md).
