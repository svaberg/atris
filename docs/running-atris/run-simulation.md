# Run the simulation

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process and inspect results](process-results.md).

Start with a [prepared simulation](prepare-simulation.md). Its planetary model,
particles, sampling, optional phantoms, physics list, and output choices are
shared by every execution method below. Moving to a different machine does not
require choosing the physics again.

| Execution environment | Job setup |
| --- | --- |
| [Local computer](run-locally.md) | Choose threads and run in a terminal |
| [Server or workstation](run-on-server.md) | Connect over SSH, share resources, run in the background, monitor and resume |
| [HPC cluster](../hpc.md) | Request nodes and cores through a scheduler, launch workers, handle wall-time limits |

Start with an existing `chunks.txt` and species `.chunk.mac` files. If they
are not ready, [create the chunk plan](plan-chunks.md) before launching workers.
Keep that plan when resuming after an interruption.

## Run a few chunks first

Follow the guide for your environment to run selected entries with `--entry`.
Start with a small subset, including each particle species you intend to use.
Each command stops after its selected chunk, leaving the remaining plan pending.
The [workflow tutorial](../tutorials/files-through-workflow.md#6-plan-and-run-chunks)
shows one proton chunk and one alpha chunk of the Earth example.

Next, [gather, process, and inspect](process-results.md) the completed chunks.
Check the input plots and initial responses, and measure the time and output
size per chunk. Decide whether the setup is worth continuing before launching
all remaining work. A few chunks check the setup and execution; they do not
establish statistical convergence.

## Continue the run

After [reviewing the first results](process-results.md#decide-whether-to-continue),
use your environment's instructions to launch the remaining plan:
[locally](run-locally.md#continue-and-monitor),
[on a server](run-on-server.md#keep-a-chunked-run-running-after-logout), or
[through Slurm](../hpc.md#submit-a-prepared-simulation-with-slurm).
Keep the same inputs, plan, physics list, output mode, and output format.
Completed chunks are skipped and remain available for the next gather.

If the first results suggest changes, revise the setup before continuing.
[Review which existing outputs still apply](process-results.md#decide-whether-to-continue)
when reusing the run directory.

Continue gathering and inspecting while more chunks run. Once you intend the
whole plan to be finished, use `atris-run . --check-complete` to verify it.
That check is not required for intermediate inspection, and finishing the
plan does not by itself establish sufficient statistics.

```{toctree}
:hidden:

run-locally
run-on-server
../hpc
```


**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process and inspect results](process-results.md).
