# Development

Version 3.0 added scatter-gather support and placed the existing Python scripts
in a small package. Structural work should not change scientific or numerical
behaviour unless that change is explicitly documented and validated.

## C++ conventions

AtRIS aims to follow Geant4's [example coding guidelines][g4-example-style] and
[modern C++ guidance][g4-modern-cpp] so that its C++ code is familiar to Geant4
users and contributors. New and modified code should use `UpperCamelCase`
member functions, `fUpperCamelCase` data members, `lowerCamelCase` local
variables and arguments, and `kUpperCamelCase` named compile-time constants.
Use `constexpr` for values known at compile time and `const` for other values
that do not change.

Existing code should be brought into line incrementally when related work is
already changing it. Non-obvious numerical boundaries and scientific constants
must be given descriptive names or explained where they are used; their meaning
should not have to be inferred from a value such as a PDG particle code.

[g4-example-style]: https://geant4.web.cern.ch/collaboration/working_groups/novextExamples/codingGuidelines.v2.2.html
[g4-modern-cpp]: https://geant4.web.cern.ch/assets/c11_guidelines.pdf

## Remaining goals

The remaining goals are:

- Move persistent simulation configuration into a composable tree of Geant4
  macro files.
- Reduce duplicated files and make the role of each retained dataset explicit.
- Provide small, reproducible system tests for installation and complete
  workflows.
- Protect existing scientific behaviour with numerical regression tests.

## Phantom data

The repository now has one `phantoms/` library. Its named response and counting
tables are source data. Run preparation selects entries from that library and
stages them under their descriptive filenames; the run's `phantoms.txt` records
the selected stems, masses, and areas, with row order assigning IDs. Generated
species macros name the response and counting files explicitly.

The same directory still contains old response tables, variance tables, plots,
and other historical data. Their provenance and continuing role should be
established before removing them. The development notebook and historical
library notes are now in the [phantom library reference](reference/phantom-library.md).

## Companion Python package

The repository now contains an initial `atris_tools` package. It provides
command-line entry points for atmosphere conversion, PSF-to-GDML conversion,
macro generation, chunk scattering and gathering, post-processing, and
plotting. These commands are also importable as Python modules.

The package uses `atris-*` command names for these operations. Existing
standalone command names remain available for compatibility and to preserve the
current user documentation. New commands should use the `atris-` prefix.

The package now separates atmosphere preparation, PSF-to-GDML conversion,
macro generation, chunk management, numerical post-processing, and plotting.
The C++ executable remains the scientific simulation core; the Python package
prepares its inputs and manages the surrounding workflow.

## Simulation preparation interface

Each species macro is currently a self-contained run entry point. It names the
GDML geometry, energy-bin file, output destination, and every phantom response
file, as well as the physics list, output mode, output format, histogram
dimensions, and random seeds. The executable takes one explicitly selected
macro-file argument; it does not infer files from a prefix.
Thread counts, worker assignments, deadlines, and scheduler limits remain
execution settings.

For chunks, `atris-scatter` derives a shared species chunk macro whose output
and seed commands use aliases. `atris-run` supplies those aliases in a temporary
wrapper macro for each plan entry. This keeps chunk scheduling outside the C++
executable while preserving a complete macro command stream for every run.

The longer-term goal is to allow the complete persistent run configuration to
be composed as a tree of `.mac` files. A future shared top-level macro could
hold campaign-wide settings and execute particle-specific or chunk-specific
macros. That orchestration is not part of the current first stage: `protons.mac`
and `alphas.mac` remain the direct entry points.

A complete simulation may be written as one macro or composed from other macros
with Geant4's `/control/execute` command. AtRIS should not require particular
macro filenames or a fixed include hierarchy. If a shared top-level structure
is introduced later, the Python tools should generate it while leaving users
free to organize equivalent macros differently.

The division into files is therefore user configuration, not part of the C++
runtime model. `atris_tools` is responsible for creating, splitting, updating,
and linking macro files with `/control/execute`; the executable consumes the
resulting command stream without needing to know which source file supplied a
command.

A Python preparation tool should also be able to expand a composed macro tree
recursively into one flattened macro for a specific execution. The flattened
file should preserve command order and mark the source of each expanded
section. It is a generated record, not the canonical file to edit, and it
remains dependent on referenced scientific data files such as GDML and
response tables.

For parallel execution, a future scatter implementation may write
worker-specific top-level macros. Each generated macro would contain only the
chunk executions assigned to that worker, so AtRIS would not need worker-count,
worker-index, or modulo-dispatch logic. Such worker macros would be generated
execution artifacts rather than the authoritative species configuration.

Phantom responses are declared independently in the generated macro. Each
command retains the phantom stem, response name, accumulation rule, and source
table:

```text
/atris/phantom/response ramona_zero_0.060MeV_detA dos energy ramona_zero_0.060MeV_detA_response.txt
/atris/phantom/response ramona_zero_0.060MeV_detA equi radiation-weighted-energy ramona_zero_0.060MeV_detA_response.txt
/atris/phantom/response ramona_zero_0.060MeV_detA rates coefficient ramona_zero_0.060MeV_detA_counting.txt
```

Mass and cross-sectional area describe the phantom itself and remain in
`phantoms.txt` for post-processing. A phantom owns an arbitrary collection of
named response channels rather than two fixed radiation and counting fields.
Each channel identifies its table and the calculation that applies its
coefficients at a particle crossing. Multiple channels can reuse one table;
the executable caches that table rather than loading another copy.

The channels' numerical values and table schemas are independent. Channels
with matching particle and energy indexing may share one lookup for efficiency,
but this is an implementation optimization rather than a format requirement.

The phantom stem identifies configuration and output. Macros refer directly to
the named response files. Run preparation may copy those files or create
ordinary symbolic links that retain their names, and users may equivalently
stage them with `ln -s`.
Numbered aliases such as `radiation_phantom0.txt` and
`counting_phantom0.txt` have been removed with the executable's filename
discovery logic.

Phantom definitions are usually shared by proton and alpha simulations. The
current generator writes the explicit file commands into both species macros.
A future shared macro may hold them once. Once the macro configuration is
authoritative, mass, area, name, and response paths should also be retained in
output metadata so that downstream tools do not have to reconstruct the run
configuration from filenames.

The Python preparation tools should create and update these macro files. They
should not become a second runtime configuration system: after preparation,
the macro tree and the referenced scientific input files should record what the
AtRIS executable will run. Scheduler limits, worker allocation, and similar
execution concerns remain outside the persistent simulation configuration.

The name `atris-generate-macros` also needs reconsideration. The command already
prepares geometry copies and energy bins as well as macros, and would then
define more of the simulation configuration. Its name should describe preparing
simulation inputs rather than generating one particular file format. The
replacement name and configuration format are still to be decided.

## Future development: adaptive energy-range chunks

The current chunk plan repeats the same source-energy distribution with new
random seeds. All chunks of a species share one chunk macro and identical
histogram axes. This is useful for restarts and parallel execution, but it
cannot direct additional simulation effort towards the energy intervals where
another primary history would reduce the final uncertainty most.

A future chunk format should treat completed chunks as additive building
blocks of one canonical response matrix. The run would retain complete proton
and alpha energy grids, while each chunk could select a contiguous subset of
those bins and its own event count. The selection changes where computation is
spent; it does not change the definition of the final response.

Combining histograms with different binning is common and remains a valid
post-processing option. It is exact when the source bins align with the target
edges, such as when fine bins are combined into coarser bins. When edges do not
align, redistributing an already accumulated bin requires an assumption about
the values within that bin and therefore loses information. The canonical
world grid is intended to make routine chunk gathering exact and reproducible,
not to prohibit deliberate rebinning or statistical combination on another
grid. Any such conversion should preserve available uncertainties and make its
interpolation or redistribution assumptions explicit.

The plan should store canonical bin indices rather than independent
floating-point limits. For example, a versioned plan entry could contain the
particle species, two random seeds, an inclusive first-bin index, an exclusive
stop-bin index, and an event count. User-facing energy limits would be resolved
to exact edges of the canonical grid when the entry is created. This prevents
nearly equal edges, incompatible bin widths, and proton/alpha energy-scaling
conventions from making apparently compatible chunks impossible to combine.
Legacy three-field plan entries could continue to mean a full-range chunk
using the existing shared chunk macro.

### Chunk execution

Each ranged chunk should run in an isolated temporary working directory. The
runner would stage links to the fixed geometry and phantom inputs, write a
local slice of the species `.bins` file, and generate a local chunk macro with
the requested energy range and event count. Output would still be written to
the run's central `chunks/` directory. Private working directories prevent
concurrent workers from replacing one another's macros or energy grids.

This arrangement can initially use the existing C++ input-prefix behaviour;
the orchestration changes can remain in the Python tools. Local energy axes
also avoid writing the full energy-by-detector matrix for a chunk that samples
only a small part of it.

### Range-aware gathering

`atris-gather` would use the run-level `.bins` file as the canonical output
axis. For every completed chunk it would:

1. verify that the local energy edges are an exact contiguous slice of the
   canonical grid;
2. map the local primary counts and raw response sums into the corresponding
   canonical rows; and
3. add those raw accumulators before any response normalization.

Overlapping chunks would improve the statistics of the same energy bins, and
disjoint chunks would fill different parts of the response matrix. Bins with
no primary histories must remain explicitly unsampled, normally represented
as `NaN` after post-processing rather than as zero response. Local energy
underflow or overflow entries would make the mapping ambiguous and should
therefore cause gathering to fail.

Histograms without a primary-energy axis, such as source direction and source
position, can continue to be added directly. Both CSV and ROOT gathering
should follow the same mapping and validation rules.

Structural compatibility means that each stored quantity can be mapped into
the same result bins and channels and combined without guessing, interpolation,
or physical assumptions. It requires matching quantities and units,
dimensionality, axis meanings and ordering, and stored statistic and
normalization state. Bin edges must either match or map exactly onto a common
grid, and detector, phantom, and response-channel identifiers must have an
unambiguous correspondence. Different event counts are compatible when the
corresponding primary counts or other required normalization information are
retained. CSV and ROOT storage are not structural differences once their
readers have produced the same internal histogram representation.

Scientific configuration is separate from structural compatibility. Seeds,
event counts, source spectra, source positions and directions, particle
populations, physics lists, and geometries may differ while the stored results
remain structurally mergeable. Such a merge represents a weighted mixture of
the contributing simulations. For example, structurally compatible SEP and
GCR chunks may intentionally be combined, although their separate
contributions cannot be recovered from the aggregate unless that distinction
is retained as an output dimension.

`atris-gather` should reject only corrupt data or data that cannot be mapped
and added unambiguously. Differences in scientific configuration should be
reported as warnings and recorded in the gathered metadata, but should not
prevent gathering. No override is needed: gathering creates a derived result
and retains the original chunks, so the user can inspect, regroup, or gather
them again without rerunning the simulation.

### Choosing valuable follow-up chunks

Range-aware chunks provide the mechanism for adaptive simulation but do not by
themselves decide where to spend more computation. An initial pilot should
include at least two independent contributions to every energy bin so that the
tools can estimate variation between chunks. For each energy bin, the planning
tools could then report:

- accumulated primary histories;
- response uncertainty estimated from independent chunk means;
- measured computation time per primary; and
- contribution to uncertainty after convolution with one or more supplied
  physical spectra.

A follow-up priority can be defined as the predicted reduction in the selected
final uncertainty divided by the predicted additional runtime. The supplied
physical spectra would influence only the allocation of future histories; they
would not be folded into or otherwise specialize the gathered response matrix.
Konstantin's later convolution with measured spectra would therefore remain
possible.

The planner must retain a minimum exploration allocation. A sparse energy bin
that has not yet produced an interaction is not evidence that its true response
is zero. Adjacent high-priority bins can be grouped into one practical chunk so
that Geant4 initialization time does not dominate many tiny simulations. The
existing per-run timing output can provide the setup and transport measurements
needed for this decision.

Development should proceed in stages: first add manual ranged chunks and a
backward-compatible plan parser; then implement and test range-aware gathering;
then expose per-energy convergence and cost diagnostics; and only then add a
tool that recommends or appends the next highest-value chunks. Numerical tests
should cover overlapping ranges, disjoint ranges, unsampled gaps, incompatible
edges, and equivalence between a full-range aggregate and the same raw
histories divided among ranged chunks.

## Simulation output

The simulation filename selects Geant4's analysis backend; CSV is the default
when no extension is supplied. Mode 0 adds the `interfaces` ntuple and mode 1
also adds the `steps` ntuple. With ROOT selected, Geant4 stores these products
and the histograms in one file and merges worker-thread objects. The
interface columns contain particle, interface, angle, crossing-energy, and
primary-energy values. The step columns contain event and track identifiers,
particle and detector identifiers, pre- and post-step positions and energies,
energy deposition, step length, time, primary energy, and process names. The
Python tools read this output with Uproot and process the larger step table in
bounded chunks.

Some modules still retain names and implementation details from the original
standalone scripts. Further cleanup should favor clear importable functions and
small command-line entry points without changing the supported workflow.

### Executable interface migration

The eventual executable interface should retain two invocation forms: the
complete legacy form with `argc == 5`, and the new run-name form with one
user-supplied argument (`argc == 2`). The currently accepted intermediate
argument counts are transitional. Keep them until the run-file path and its
calling tools are complete; do not make them part of the final interface.

## Thread scaling

Do not assume that AtRIS becomes faster whenever more worker threads are added.
The imported README (commit `112e4dc`) says that scaling eventually stops
because of CPU cache topology. It does not give the limiting core count. The
accompanying `simstarter.ipynb` uses 16 worker threads. That is a historical
example, not a benchmark for current hardware.

The thread count applies to each AtRIS process. Therefore, an HPC chunk using
16 worker threads requires 16 cores, and concurrent chunks require separate
sets of cores. Benchmark representative chunks at several thread counts before
deciding how many cores to allocate to each chunk. Guidance for chunk sizing, scheduler worker
pools, and resource measurement is in
[Running AtRIS on an HPC system](hpc.md).

## Remaining tests

Temporary end-to-end harnesses are not part of the supported Python interface.
Useful harnesses should be converted into reproducible smoke or system tests;
those that do not provide lasting test coverage should be removed.

The current tests cover the Python tools and short runs of the compiled AtRIS
executable. The main remaining gaps are a complete preparation-to-post-processing
system test, behavioral tests for the Slurm wrappers, and reviewed numerical
regression baselines for scientific output.

See [Minimal test fixture](reference/minimal-test-fixture.md) for the fixture
layout and the limits of its validation.

The [workflow tutorial](tutorials/files-through-workflow.md) exercises preparation,
execution, and processing using a few chunks of the Earth example. It checks
the workflow, not scientific convergence.
