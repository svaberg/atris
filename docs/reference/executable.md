# AtRIS executable

```text
AtRIS <simulation-name>
AtRIS <physics-list> <simulation-name> <mode> [phantom-count]
AtRIS --version
```

The one-argument form is the normal interface. Run it from the directory
containing the simulation inputs and numbered phantom files:

```bash
AtRIS protons
```

This reads `protons.gdml`, `protons.bins`, and `protons.mac`. The macro must set
the physics list with `/atris/physicsList` and the named output mode with
`/atris/outputMode` before `/run/initialize`. AtRIS executes the macro once;
these commands configure the same Geant4 run that the remainder of the macro
starts.

AtRIS also discovers complete `radiation_phantomN.txt` and
`counting_phantomN.txt` pairs in the current directory. IDs must be contiguous
from zero. Files beginning with `protons` receive the outputs. Existing output
names can be overwritten.

The complete legacy form remains accepted:

```bash
AtRIS FTFP_BERT_HP protons -1 2
```

| Argument | Meaning |
| --- | --- |
| `physics-list` | Legacy Geant4 reference physics-list name, for example `FTFP_BERT_HP`. Availability depends on the linked Geant4 installation. An unrecognized name prints the available reference lists and exits unsuccessfully. If the macro contains `/atris/physicsList`, its value must match. |
| `simulation-name` | Input prefix and output filename, or a seeded chunk name as described below. An optional filename extension selects the Geant4 output backend. |
| `mode` | Legacy integer output mode from the table below. If the macro contains `/atris/outputMode`, its named value must match. |
| `phantom-count` | Optional compatibility check against the staged phantom pairs discovered by the executable. It does not read `phantoms.txt`. |

Newly generated macros begin with the pre-initialization commands
`/atris/physicsList NAME`, `/atris/outputMode NAME`,
`/atris/directionBins NPHI NCOS`, and `/atris/positionBins NPHI NCOS`. They
record the physics list, output mode, and source histogram dimensions with the
run inputs. In the legacy form, AtRIS stops before `/run/initialize` if the
physics list or output mode differs from the command-line argument. A nonpositive
bin count also stops either form. Older macros without the configuration
commands remain usable through the legacy interface and use the existing 120
by 60 source histogram dimensions.

The transitional legacy form without the explicit phantom count also remains
accepted:

```bash
AtRIS FTFP_BERT_HP protons -1
```

In the complete legacy example, `2` must match the two staged pairs. AtRIS
exits with an error if the count differs, either member of a pair is missing,
or the IDs contain a gap. With no staged phantom files, the discovered count is
zero.

With no filename extension, the output format defaults to CSV. An explicit
extension is passed to Geant4, independently of the output mode. In the
one-argument form, `profile` and `shower` select ROOT when no extension is
given:

```bash
AtRIS protons.csv
AtRIS protons.root
```

Both commands use the same `protons.*` input files. Geant4 selects and validates
the requested backend. AtRIS exits with an error when the extension is unknown
or the installed Geant4 lacks the requested optional backend.

## Output modes

| Integer | Macro name | Products |
| --- | --- | --- |
| `-1` | `response` | Primary, source-position, source-direction, ionizing and total energy-deposition, and phantom response histograms. |
| `0` | `profile` | The same histograms plus interface-crossing records. |
| `1` | `shower` | The same products plus transport-step records in sensitive volumes. |

Use only these three modes. Other integers are not explicitly rejected but
have no documented contract. Step output includes steps in the terminating
sensitive layers, before the track is killed; it does not record steps in
non-sensitive world space. See [Output files](outputs.md) for schemas.

## Seeded chunk names

A basename ending in two underscore-separated, exactly six-digit decimal
fields is interpreted as `<prefix>_<seed1>_<seed2>`:

```bash
AtRIS chunks/protons_123456_654321
```

The full argument, including an optional output extension, selects the output.
Input lookup uses the suffix-free, stripped basename in the current directory:
`protons.gdml`, `protons.bins`, and
`protons.chunk.mac` if it exists, otherwise `protons.mac`. The directory part
of a seeded name does not select an input directory. Both seeds are set before
the macro executes; a later `/random/setSeeds` command in that macro can
replace them. `atris-scatter` removes that command from generated chunk macros.

For an ordinary, unseeded name, its path is retained when locating inputs.
The parent directory of an output prefix must already exist.

## Status and diagnostics

`AtRIS --version` prints the compiled version. A successful macro execution
returns `0`; a failed macro execution returns `1`. Phantom loading and output
opening failures also return `1`. Wrong argument count prints usage but
currently returns `0`, so a zero status alone is not evidence that a simulation
ran. Malformed integer arguments can fail before execution.

The executable writes diagnostics to standard output/error. It does not itself
create a `.log` file; `atris-run` redirects both streams to a per-chunk log.

At completion, AtRIS reports the wall time spent executing the Geant4 macro,
the setup and cleanup time outside that macro, and their total. The macro
interval uses the reported worker count but can still include serial Geant4
initialization, coordination, and output work; it is not pure parallel CPU
time.

Implementation: `src/main.cc`, `src/HistoManager.cc`, and
`src/SensitiveDetector.cc`.
