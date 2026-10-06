# Runtime settings

## Environment variables

| Variable | Consumer | Effect |
| --- | --- | --- |
| `G4FORCENUMBEROFTHREADS` | Geant4 run manager | Forces the worker-thread count for each AtRIS process. |
| `ATRIS_ROOT` | Phantom staging | Default phantom archive is `$ATRIS_ROOT/phantoms`. |
| `PATH` | Shell, runner, version reporting | Locates `AtRIS` and the Python commands. |
| `GEANT4_DATA_DIR`, `G4LEDATA` | `setup_atris.sh` | If either points to an existing directory, the script keeps the already loaded Geant4 environment. Otherwise it sources the adjacent installation. |
| `MPLBACKEND` | Plotting | Defaults to `Agg` if unset, allowing PNG creation without a display. |

`setup_atris.sh` derives `ATRIS_ROOT` from its own location, prepends the
checkout's `build/` to `PATH`, and sources the sibling Geant4 installation if
needed. It retains Python commands already on `PATH`; if `atris-run` is absent,
it attempts to add Python's user command directory. Geant4 dataset variables
are managed by the Geant4 setup script.

The [HPC guide](../hpc.md#environment-and-worker-launch) documents the Slurm
wrapper's variables, resource requests, and safety interval alongside the
complete example script.

## Thread precedence

1. A valid `G4FORCENUMBEROFTHREADS` forces the Geant4 thread setting. Use a
   positive integer; Geant4 11.4 also accepts `max` or `MAX` for all detected cores.
2. Otherwise AtRIS initially selects all cores detected by Geant4.
3. A valid `/run/numberOfThreads` command in the macro can change that initial
   setting when no environment override is set. Put it before initialization.

The count is per AtRIS process. The Python runner's `--worker-count` describes
how many processes are launched externally and only partitions the chunk plan;
it neither starts those processes nor selects their thread counts.

## Random seeds

| Setting | Meaning |
| --- | --- |
| `atris-generate-macros --random-seed S` | Seeds Python's generator of the two Geant4 seeds written into each ordinary macro. |
| `atris-scatter --random-seed S` | Seeds the generator of unique seed pairs in a new plan or extension. |
| `/atris/randomSeeds A B` | Sets the Geant4 random engine's seeds and records them in output metadata. |

AtRIS selects CLHEP's `MTwistEngine`. Generated seed values are between 31 and
999999 inclusive. Chunk plans format each as six digits. Seed pairs are unique
across both species in a generated plan and its extensions.

Generated `.chunk.mac` files use seed aliases. `atris-run` fills those aliases
from `chunks.txt` before executing the shared macro. Omitting a Python
`--random-seed` uses a fresh generator state. Reproducibility also requires
retaining the physics configuration, inputs, software versions, and run
settings; a seed by itself is not a complete run specification.

## Logging and version reporting

Most Python commands write progress messages, warnings, and errors to standard
error. `--quiet` hides progress messages but still shows warnings and errors.
`--verbose` also shows debugging details. You cannot use both options together.
The command reference lists which tools support these options. ROOT ntuple
dumps are written as CSV to standard output for piping or redirection.

Modern `atris-*` commands accept `--version` to report the Python package and
available executable versions. `AtRIS --version` reports only the compiled
executable version. Legacy aliases do not add the modern `--version` option.

Implementation: `setup_atris.sh`, `src/main.cc`, `atris_tools/cli.py`,
`atris_tools/version.py`, and
`examples/slurm/run-atris.slurm.sh`.
