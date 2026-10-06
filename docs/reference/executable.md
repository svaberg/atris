# AtRIS executable

```text
AtRIS <macro-file>
AtRIS --version
```

Run the executable from the prepared run directory and give it the macro to
execute:

```bash
AtRIS protons.mac
```

The macro names every file used by that run. A generated proton macro starts
with commands of this form:

```text
/atris/geometryFile protons.gdml
/atris/energyBinsFile protons.bins
/atris/outputFile protons
/atris/phantom/response ramona_zero_0.060MeV_detA dos energy ramona_zero_0.060MeV_detA_response.txt
/atris/phantom/response ramona_zero_0.060MeV_detA equi radiation-weighted-energy ramona_zero_0.060MeV_detA_response.txt
/atris/phantom/response ramona_zero_0.060MeV_detA rates coefficient ramona_zero_0.060MeV_detA_counting.txt
/atris/physicsList FTFP_BERT_HP
/atris/outputMode response
/atris/outputFormat csv
/atris/directionBins 120 60
/atris/positionBins 120 60
/atris/randomSeeds 123456 654321
/run/initialize
```

Geometry, energy bins, output, and phantom tables do not have to share the
macro's basename. Paths are interpreted relative to the directory in which
AtRIS is run. Each phantom response command supplies a phantom stem, response
name, accumulation mode, and table path. A phantom can have any number of
uniquely named responses. Omit these commands for a run without phantom
responses.

The pre-initialization commands must precede `/run/initialize`. The rest of the
macro configures the Geant4 source and starts transport with `/run/beamOn`.
AtRIS executes the selected macro once and does not search the run directory
for inputs.

## Output modes

| Integer stored in output | Macro name | Products |
| --- | --- | --- |
| `-1` | `response` | Primary, source-position, source-direction, ionizing and total energy-deposition, and phantom response histograms. |
| `0` | `profile` | The same histograms plus interface-crossing records. |
| `1` | `shower` | The same products plus transport-step records in sensitive volumes. |

Step output includes steps in the terminating sensitive layers before a track
is killed; it does not record steps in non-sensitive world space. See
[Output files](outputs.md) for the schemas.

The `/atris/outputFormat` command selects the Geant4 analysis backend. CSV
response output is written as several files beginning with the configured
`/atris/outputFile` value. ROOT output is written to that value with a `.root`
extension. The output's parent directory must already exist.

## Chunk execution

`atris-scatter` makes a shared `<species>.chunk.mac`. Its output filename and
random-seed commands use Geant4 aliases. For each plan entry, `atris-run` writes
a temporary wrapper macro that defines those aliases and executes the shared
species macro. The wrapper is then removed. The executable still receives one
ordinary macro argument; it does not parse species or seeds from an output
filename.

## Status and diagnostics

`AtRIS --version` prints the compiled version. A successful macro execution
returns `0`; a failed command or simulation returns nonzero. A wrong argument
count prints `AtRIS <macro-file>` usage to standard error and returns nonzero.

The executable writes diagnostics to standard output and error. It does not
create a log itself; `atris-run` redirects both streams to one log per chunk.

At completion, AtRIS reports wall time for macro execution, setup and cleanup,
and the total. The macro interval includes serial Geant4 initialization,
coordination, and output work as well as particle transport.

Implementation: `src/main.cc`, `src/RunConfiguration.cc`,
`src/PhantomResponses.cc`, `src/HistoManager.cc`, and
`src/SensitiveDetector.cc`.
