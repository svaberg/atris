# atris-run

Run the incomplete entries assigned to one worker in a scattered run.

```bash
atris-run .
atris-run . --entry 17
atris-run . --check-complete
```

**Inputs:** `chunks.txt`, the species `.chunk.mac` files and every file they
name, plus optional `phantoms.txt` metadata for progress logging. **Outputs:**
per-chunk histograms, optional ROOT particle ntuples, logs, and completion
markers under `chunks/`.

Defaults are the current directory and one worker with index zero. Supply
`--worker-index` and `--worker-count` together. `--entry` uses a one-based plan
line; worker indices are zero-based. Each species macro supplies the physics
list, output mode, input paths, and phantom paths to AtRIS. For each chunk, the
runner supplies its output name and seed pair through a temporary wrapper macro.

The runner finds `AtRIS` on `PATH`. It skips completed entries and stops the
worker on a failed subprocess. `--deadline` is an absolute Unix timestamp;
`--stop-before-end` defaults to zero seconds and requires a deadline when
nonzero. The deadline is checked even with a zero safety interval. Neither
option interrupts a running chunk.

`--check-complete` performs no simulation and checks the entire plan, returning
0 when all markers exist and 1 when any are missing. It does not restrict the
check to `--entry` or a worker shard. See [chunk semantics](../chunks.md) and
[thread settings](../runtime.md).

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-run [-h] [--entry NUMBER] [--worker-index INDEX]
                 [--worker-count COUNT] [--stop-before-end SECONDS]
                 [--deadline UNIX_TIME] [--check-complete] [-q | -v]
                 [--version]
                 [RUN_DIRECTORY]

Run the incomplete entries assigned to one worker from an AtRIS chunk plan,
marking each successful chunk complete.

positional arguments:
  RUN_DIRECTORY         Scattered run directory (default: current directory).

options:
  -h, --help            show this help message and exit
  --version             Show the AtRIS and atris-tools versions and exit.

Chunk plan and worker options:
  --entry NUMBER        Run only this one-based chunks.txt entry instead of a
                        worker shard. A completed entry is still skipped.
  --worker-index INDEX  Zero-based rank used to select this worker's
                        round-robin shard; must be supplied with
                        --worker-count (default: 0).
  --worker-count COUNT  Number of externally launched workers sharing the
                        plan; must be supplied with --worker-index (default:
                        1).
  --stop-before-end SECONDS
                        Do not start another chunk within SECONDS of
                        --deadline (default: 0).
  --deadline UNIX_TIME  Absolute Unix timestamp at which the external
                        allocation ends; used only with --stop-before-end.
  --check-complete      Do not run anything; return success only when every
                        chunks.txt entry has a completion marker.

Logging options:
  -q, --quiet           Suppress normal progress; show warnings and errors
                        only.
  -v, --verbose         Include detailed per-file, per-request, or per-chunk
                        progress.

Examples:
  atris-run runs/earth
    Run every incomplete chunk sequentially.

  G4FORCENUMBEROFTHREADS=7 atris-run runs/earth \
    --worker-index 2 --worker-count 11 \
    --deadline "$JOB_END_TIME" --stop-before-end 1800
    Run worker index 2's round-robin shard of an 11-worker pool with seven
    Geant4 threads. It does not start a new chunk during the allocation's
    final 30 minutes. Launch the other worker indices externally.

  atris-run runs/earth --entry 17
    Run only plan entry 17 unless it is already complete.

  atris-run runs/earth --check-complete
    Check whether every planned chunk has a completion marker.

The command reads chunks.txt, uses phantoms.txt when present for progress
labels, skips entries with an existing .COMPLETE marker, and runs selected
entries sequentially. Worker coordinates select a collision-free shard; they
do not launch workers or control Geant4 threads. A deadline is checked only
before a chunk starts and never interrupts a running chunk. Failed chunks are
left incomplete. Each species macro selects its physics list, output mode, and
other run settings. This command does not gather or post-process results.
```

Implementation: `atris_tools/run_chunks.py`.
