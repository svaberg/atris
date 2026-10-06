# atris-clone

Copy reusable inputs into a new run directory without copying results.

```bash
atris-clone runs/earth runs/earth-new
```

The source must exist and contain recognized inputs. The destination must not
exist, and its parent must exist. Selected files are `simulation.psf`,
`phantoms.txt`, `nrlmsis_output.txt`, and matches for:

```text
*.gdml  *.mac  *.bins  *.spec
*_response.txt  *_counting.txt
```

Internal symlinks are rebased to the new directory; external targets remain
external. Logs, output tables, chunk plans, and markers are not copied.
The `*.mac` pattern does copy `.chunk.mac` files, although no chunk plan is
copied. If cloning an already scattered run, those files conflict with creating
a fresh plan via `atris-scatter --chunks`; preferably clone prepared inputs
before scattering. No simulation or input regeneration is performed.

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-clone [-h] [-q | -v] [--version] SOURCE DESTINATION

Create a new AtRIS run directory from the reusable inputs in an existing run.

positional arguments:
  SOURCE         Existing run directory containing reusable AtRIS inputs.
  DESTINATION    New run directory to create.

optional arguments:
  -h, --help     show this help message and exit
  -q, --quiet    Suppress normal progress; show warnings and errors only.
  -v, --verbose  Include detailed per-file, per-request, or per-chunk progress.
  --version      Show the AtRIS and atris-tools versions and exit.

Simulation results, chunk plans, completion markers, and logs are not copied. The
destination must not already exist. Symbolic links among copied inputs are preserved
and rebased when their targets are also inside the source run. This command prepares a
starting point; it does not run or scatter the simulation.
```

Implementation: `atris_tools/clone_run.py`.
