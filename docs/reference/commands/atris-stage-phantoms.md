# atris-stage-phantoms

Stage the selected response tables under their descriptive names.

**Input:** `RUN_DIRECTORY/phantoms.txt` plus the named radiation/counting tables.
**Outputs:** `<stem>_response.txt` and `<stem>_counting.txt` relative symlinks
or local copies.
The run directory argument is required.

```bash
atris-stage-phantoms . --copy
```

Lookup checks the run directory first, then `--archive`, or
`$ATRIS_ROOT/phantoms` when no archive is specified. By default the command
creates relative symbolic links under the original descriptive filenames;
`--copy` makes local files instead. Regular destination files are not
overwritten. Obsolete numbered symlinks from older AtRIS versions are removed.

`--accept-missing-counting` creates a local all-ones counting table only when
a real counting table cannot be found. Per-phantom staging errors are logged
and processing continues with other IDs; a successful command exit alone does
not certify that every requested phantom was staged. A missing metadata file
selects no phantoms. See [phantom formats](../inputs.md#phantom-selection).

## Arguments and options

The following is the command's `--help` output for this revision.

```text
usage: atris-stage-phantoms [-h] [--archive DIRECTORY] [--copy]
                            [--accept-missing-counting] [-q | -v] [--version]
                            RUN_DIRECTORY

Stage the phantom response and counting tables selected by phantoms.txt under
their descriptive filenames.

positional arguments:
  RUN_DIRECTORY         Run directory containing phantoms.txt.

options:
  -h, --help            show this help message and exit
  --archive DIRECTORY   Directory containing the named phantom tables. Files
                        in the run directory are checked first; the default
                        archive is $ATRIS_ROOT/phantoms when ATRIS_ROOT is
                        set. Without either, only the run directory is
                        searched.
  --copy                Copy the named phantom tables into the run directory
                        instead of creating relative symbolic links.
  --accept-missing-counting
                        Accept a missing counting-response table by creating a
                        local dummy table whose counting values are all one. A
                        real counting table is always used when available.
  -q, --quiet           Suppress normal progress; show warnings and errors
                        only.
  -v, --verbose         Include detailed per-file, per-request, or per-chunk
                        progress.
  --version             Show the AtRIS and atris-tools versions and exit.

Each phantoms.txt row must contain file stem, mass, and area; row order
defines zero-based phantom IDs. The command does not create radiation-response
tables or change phantoms.txt. Symbolic links are updated to match the current
selection, while regular destination files are not overwritten. An error in
one row does not prevent other rows from being staged.
```

Implementation: `atris_tools/phantoms.py`.
