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

The macro names every file used by that run. Generated macros are ordered in
the same phases in which Geant4 consumes them:

1. AtRIS input files, physics, output, histogram resolution, phantom responses,
   and random seeds.
2. Geant4 initialization and transport controls.
3. General Particle Source particle, energy, position, and direction settings.
4. The final event-processing command.

The file begins with a guide to its three command namespaces. Comments explain
each setting where it first appears; repeating phantom blocks share one guide
instead of repeating the same comments for every phantom. A generated macro
can therefore be read without cross-referencing this page. For example:

```text
# /atris/ configures AtRIS inputs, scoring, and output.
# /run/ initializes Geant4, controls transport, and starts events.
# /gps/ configures Geant4's General Particle Source (GPS).

# Read the detector geometry from this GDML file.
/atris/geometryFile protons.gdml
# Read output energy-bin edges; GPS source sampling is configured below.
/atris/energyBinsFile protons.bins
# Use this filename stem for all simulation output.
/atris/outputStem protons

# Use this Geant4 reference physics list for particle transport.
/atris/physicsList FTFP_BERT_HP
# Save aggregate response histograms only.
/atris/outputMode response
# Write analysis data using Geant4's csv backend.
/atris/outputFormat csv

# Each response starts with its table coefficient. The scaleBy settings choose
# which physical factors are applied; name only labels the output.
# Phantom: ramona_zero_0.060MeV_detA
/atris/phantom/name ramona_zero_0.060MeV_detA
# Response: absorbed dose (name: dos)
/atris/phantom/response/name dos
/atris/phantom/response/tableFile ramona_zero_0.060MeV_detA_response.txt
/atris/phantom/response/scaleByCrossingEnergy true
/atris/phantom/response/scaleByRadiationWeight false
/atris/phantom/response/scaleByInversePhantomMass true
/atris/phantom/response/add

# Set the two random seeds before initialization.
/atris/randomSeeds 123456 654321

# Initialize Geant4 after all /atris/ configuration is complete.
/run/initialize

# Generate this particle species.
/gps/particle proton
# Sample kinetic energy from a power-law distribution.
/gps/ene/type Pow
# Set the minimum primary kinetic energy.
/gps/ene/min 1 MeV
# Set the maximum primary kinetic energy.
/gps/ene/max 1000000 MeV
# Use an E^-1 power law, which is uniform in log kinetic energy.
/gps/ene/alpha -1

# Process the requested events with the configuration above.
/run/beamOn 363000

# End of AtRIS simulation macro.
```

Geometry, energy bins, output, and phantom tables do not have to share the
macro's basename. Paths are interpreted relative to the directory in which
AtRIS is run. `/atris/phantom/name` selects a phantom. Set the response name,
table file, and three `scaleBy` factors, then use
`/atris/phantom/response/add` to register that response. The selected phantom
remains active, while the response properties are cleared after each
successful `add`. A phantom can have any number of uniquely named responses.
Omit these commands for a run without phantom responses.

The pre-initialization `/atris/` commands must precede `/run/initialize`.
Initialization makes the `/gps/` source commands available. The final
`/run/beamOn` starts transport. AtRIS executes the selected macro once and does
not search the run directory for inputs.

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
`/atris/outputStem` value. ROOT output is written to that value with a `.root`
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
