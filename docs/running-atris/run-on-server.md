# Run on a server or workstation

**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).

Use this guide for an SSH session on a shared machine without a job scheduler.
For a scheduled cluster allocation, use the [HPC guide](../hpc.md).

## Prepare the session and inputs

Log in, load the installed AtRIS/Geant4 environment, and change into your
[prepared simulation directory](prepare-simulation.md). For Ivan's installation,
login, and resource guidance, see [UiO setup](use-atris-on-uio.md). Transfer the
whole prepared directory if it was created elsewhere, including the targets of
any phantom links. Preparation with `atris-stage-phantoms --copy` keeps those
targets local.

AtRIS reads the physics list and output mode chosen during preparation from
each species macro. Check current load and the machine's resource policy before
choosing a thread count.

## Use the prepared chunk plan

Follow [chunk planning](plan-chunks.md) once in the prepared run directory.
If `chunks.txt` already exists, use that plan. The background launch below
runs incomplete chunks and preserves completed work for later resumption.

## Run a few chunks first

Start with a selected entry in the foreground:

```bash
export G4FORCENUMBEROFTHREADS=4
nice -n 10 atris-run . --entry 1
```

Choose the thread count for the machine and current load. `--entry` selects a
one-based line of `chunks.txt`; repeat with other entries to include each
particle species. Each command stops after its selected chunk. Keep the SSH
session open while it runs. For a chunk that needs to survive logout, use the
`nohup` form below with `--entry` added to restrict it to that chunk.

[Gather, process, and inspect](process-results.md) the completed subset before
launching the rest. Check the input plots, initial responses, and measured
runtime, then [decide whether to continue](process-results.md#decide-whether-to-continue).

## Keep a chunked run running after logout

After deciding to continue, change into the run directory
(the directory containing `chunks.txt`). Check `uptime` and `top` first. Use a
conservative thread count when the server is shared:

```bash
export G4FORCENUMBEROFTHREADS=4  # example: choose for this machine and current load
nohup nice -n 10 atris-run . >> atris-run.log 2>&1 < /dev/null &
```

`atris-run` does not background itself or set its own priority. Here, `nohup`
protects it from ordinary terminal hangup, `nice -n 10` lowers CPU scheduling
priority, and `&` returns the prompt. This runner executes chunks sequentially,
with one AtRIS process at a time. Each chunk uses the selected number of
Geant4 threads. The launch does not protect against a server restart or
administrator-enforced session cleanup.

### Inspect or stop the background runner

To inspect your own CPU and memory use, run:

```bash
top -u "${USER}"
```

Press `q` to leave `top`. While you are still in the shell that launched the
runner, `jobs -l` shows its shell job number. You can bring it back to the
foreground and then stop it with Ctrl+C:

```bash
jobs -l
fg %1
```

Replace `%1` with the job number shown by `jobs`. Shell job numbers belong to
the launching shell, so `fg` is not available after logging out and back in.

After reconnecting, use `top -u "${USER}"` to find the active process named
`AtRIS`; its PID is in the first column. To stop it from inside `top`, press
`k`, enter that PID, and accept signal 15. Alternatively, press `q` and run
`kill PID`, replacing `PID` with the number shown by `top`. The runner then
reports that chunk as failed and exits. The interrupted chunk has no completion
marker, so it runs again from the beginning when the runner is restarted.

Overall progress is appended to `atris-run.log`; each chunk's detailed output
is written under `chunks/`. Watch the overall log with:

```bash
tail -f atris-run.log
```

Ctrl+C stops `tail`, not the background calculation. After reconnecting, check
whether the complete plan has finished from its run directory:

```bash
atris-run --check-complete
```

If a run stops, first verify that the original runner and its AtRIS child have
exited before launching it again. Reusing the launch command skips completed
chunks and reruns unfinished chunks from their beginning. This particular
command starts an unsharded runner, so wait for it to exit before starting the
same command again; otherwise both processes may select the same chunk.


Once a chunk finishes, you can use the shared
[results-processing guide](process-results.md) to inspect completed chunks
while the background run continues.


**Previous step:** [Plan chunks and restarts](plan-chunks.md).

**Next step:** [Process the completed results](process-results.md).
