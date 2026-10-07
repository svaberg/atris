# Input files

The primary model input to the preparation workflow is `simulation.psf`.
Phantom metadata and response tables are optional. The executable reads the
species-specific GDML, macro, and bins files generated from that model and
your source settings. NRLMSIS tables are one optional source for creating a PSF.

## Run-directory filenames

| File | Consumer | Purpose |
| --- | --- | --- |
| `simulation.psf` | Macro generation, GDML conversion, post-processing | Layer geometry and material properties. |
| `simulation.gdml` | Macro generation | Geometry copied to the species-specific GDML files. |
| `<species>.gdml` | AtRIS | Geant4 geometry and sensitive-detector IDs; the macro names the file explicitly. |
| `<species>.mac` | AtRIS | File selection, Geant4 initialization, source settings, seeds, and event count. |
| `<species>.bins` | AtRIS | Primary kinetic-energy bin edges, in MeV; the macro names the file explicitly. |
| `phantoms.txt` | Staging, chunk runner, post-processing, plotting | Selection of named phantom tables, masses, and areas. |
| `<stem>_response.txt` | AtRIS | Response table named by one or more `/atris/phantom/response/file` properties. |
| `<stem>_counting.txt` | AtRIS | Counting-response table named by an `/atris/phantom/response/file` property. |
| `<prefix>.chunk.mac`, `chunks.txt` | Chunk workflow | Shared chunk macro and seed plan; see [Scatter/gather files](chunks.md). |

The Python workflow uses the species names `protons` and `alphas`. The
executable can use other prefixes, but post-processing and plotting discover
these two canonical names.

## Planet Specification Format (PSF)

A PSF is a whitespace-separated numeric table preceded by a material-definition
line. Blank and `#` comment lines may precede the table. Legacy files may put
the material definition in the first comment line instead.

From Python, `atris_tools.psf.build_psf` assembles layers from named quantities;
`write_psf` saves the result with its descriptive header and material definition.
See [Building a PSF from Python](#building-a-psf-from-python) and the
[exoplanet notebook](../tutorials/exoplanet-psf.ipynb).

For example, the NRLMSIS converter writes:

```text
O478Si284Al84Fe52Ca37Na28Mg15 N O Ar He H
```

The first token describes the legacy solid composition as element symbols
followed by relative mass weights. The GDML converter normalizes those solid
weights. Remaining tokens name the per-layer material-fraction columns in
order. Nonzero fractions define the composition of a gas, liquid, or solid
layer and are written into GDML as supplied, so provide fractions summing to
one. The NRLMSIS converter produces normalized gas fractions.

| Column (one-based) | Quantity | Unit or convention |
| --- | --- | --- |
| 1 | Inner radius | km from the planet's centre |
| 2 | Outer radius | km from the planet's centre |
| 3, 4 | Starting and ending azimuth, phi | rad; endpoints, not angular widths |
| 5, 6 | Starting and ending polar angle, theta | rad; endpoints, not angular widths |
| 7 | Sensitive-detector ID | Integer |
| 8 | Temperature | K |
| 9 | Density | g/cm³ |
| 10 | Pressure | Pa |
| 11 | Material state | `0` gas, `1` solid, or `2` liquid |
| 12 onward | Material mass fractions | One column per remaining material-definition token |

The standard workflow assumes layers ordered from the centre outward with
contiguous IDs from zero. ID `0` and the highest ID terminate tracks. The
standard generated Earth model contains an interior, crust, atmosphere, and
outer terminating layer. Macro generation places the source 0.001 km beyond
the penultimate row's outer radius.

The GDML converter requires the numeric column count to match the material
header. It uses the last row's outer radius plus 100 km as the world half-size.
Custom PSFs must also respect the post-processor's
[geometry and altitude conventions](outputs.md#geometry-and-altitude).

### Building a PSF from Python

Import `build_psf` and `write_psf` from `atris_tools.psf`. All builder arguments
are named:

| Argument | Values |
| --- | --- |
| `inner_radius_km`, `outer_radius_km` | One radius per shell, measured from the centre, in outward order |
| `temperature_k` | Temperature in kelvin |
| `density_g_cm3` | Density in g/cm³ |
| `pressure_pa` | Pressure in pascals |
| `mass_fractions` | Element-to-fraction mapping, such as `{"N": 0.8, "O": 0.2}` |
| `solid_composition` | Compact fallback composition, such as `"O533Si467"` |
| `state` | `"gas"` (default), `"solid"`, or `"liquid"` |

Except for the radii, each physical quantity and each element fraction can be a
scalar shared by every layer or an array with one value per layer. States can
also be supplied per layer. Fractions must sum to one; all-zero fractions in a
solid row select the compact fallback composition. The builder checks array
lengths, finite values, positive temperature and density, nonnegative pressure,
and non-overlapping shells. It does not normalize fractions silently.

The builder creates full spherical shells and assigns sequential IDs from zero.
It preserves gaps between shells. Interior, surface, and outer stopping layers
must be supplied explicitly; it does not add layers or calculate an atmosphere.

The returned `PSF` holds the numeric array in `.layers` and its ordered material
definition in `.materials`. The element mapping determines both column and
header order. Save it with `write_psf(path, psf)`.

For an existing NumPy table, the lower-level interface remains
`write_psf(path, layers, materials="O533Si467 N")`. It checks the table shape,
finite values, integer IDs, and material states. Both forms replace an existing
file and expect the parent directory to exist. Additional keyword arguments
are forwarded to `numpy.savetxt`; omitting `fmt` uses NumPy's own formatting.
Use `write_psf(path, psf, fmt=psf.formats("%.3e"))` for three decimal places in
scientific notation for temperature, density, pressure, and mass fractions.
The format list preserves radii and angles and writes IDs and states as integers.

Fixed column indices are defined in `atris_tools.psf`: `INNER_RADIUS`,
`OUTER_RADIUS`, `PHI_START`, `PHI_END`, `THETA_START`, `THETA_END`, `DETECTOR_ID`,
`TEMPERATURE`, `DENSITY`, `PRESSURE`, and `STATE`. `FIRST_ELEMENT` marks the
start of the mass-fraction columns, whose order comes from the material header.
Use these constants when indexing a PSF array, for example
`layers[:, DENSITY]` or `layers[:, FIRST_ELEMENT:]`.

### Layer composition

The PSF stores elemental mass fractions, not molecular abundances. For example,
`O533Si467 N O Ar` requires three fraction columns in the order nitrogen,
oxygen, argon. A gas row may end in `0 0.75 0.24 0.01`: the first value is the
material state, followed by the three mass fractions. A solid row with nonzero
fractions uses its per-layer composition. For backward compatibility, a solid
row with all-zero fractions uses the compact solid composition from the header.
Gas and liquid rows provide their composition in the per-layer columns.

Convert number or mole fractions $x_i$ to mass fractions using

$$
w_i=\frac{x_i M_i}{\sum_j x_j M_j},
$$

where $M_i$ is the mass appropriate to each atom or molecule. For molecular
species, combine their elemental mass contributions into the PSF's element
columns. The converter does not normalize per-layer fractions for you.

A compact {download}`two-layer format sample <../running-atris/examples/two-layer-atmosphere.psf>`
is available for inspecting the text layout. It is a format example, not a
physical atmosphere model. To construct a model step by step, use the
[PSF notebook](../tutorials/exoplanet-psf.ipynb).

## NRLMSIS source tables

`atris-nrlmsis-to-psf` accepts downloaded text tables with a header containing
`Year Mon Day` and these named fields:

```text
Year Mon Day DOY hour Heit Lat Lon Oden N2den O2den air T Heden Arden Hden Nden
```

Columns are selected by name, allowing extra columns. Values are interpreted
as altitude in km, species number densities in cm⁻³, mass density `air` in
g/cm³, and temperature in K. Header unit suffixes are stripped for matching;
the converter does not perform arbitrary input-unit conversion.

Input tables must share one date, time, latitude, and longitude and combine
into a complete uniform altitude grid with at least two rows. Compatible
duplicated altitudes are retained once, with relative tolerance `5e-4`.
Rejected malformed or non-positive physical rows need a valid replacement at
the same altitude. Conflicting duplicates and missing grid points are errors.
The resulting Earth model uses a 6371 km radius and a 0.02 km crust.

## GDML

See [GDML in the software ecosystem](../background/software-ecosystem.md#gdml-exchanging-geometry)
for an introduction to the format and its documentation.

AtRIS uses the GDML world and assigns sensitive detectors using auxiliary tags:

```xml
<auxiliary auxtype="SensDet" auxvalue="2"/>
```

The numeric value becomes the detector ID. AtRIS asks the Geant4 GDML parser
for the auxiliary map and counts entries whose type is `SensDet`. Keep one such
tag per sensitive layer. The histogram and terminating-layer logic assume
contiguous IDs.

## Energy bins and macros

A `.bins` file contains whitespace-separated energy edges, without a header,
in total kinetic energy MeV. Provide increasing edges. With `M` edges there
are `M-1` interior energy bins, plus underflow and overflow bins in raw output.

The generated output-bin grid is
`10**linspace(min_power, max_power, energy_points)` for protons, and four times
that grid for alphas. The GPS source is continuous rather than restricted to
those edges: it uses a power law proportional to $E^{-1}$ between the first and
last edge, which samples uniformly in $\log E$. Alpha energies in the actual
`.bins`, `.mac`, and output histograms are total particle energies, not energies
per nucleon.

Generated macros name their GDML, energy-bin, output, and phantom files with
`/atris/geometryFile`, `/atris/energyBinsFile`, `/atris/outputFile`, and the
`/atris/phantom/*File` commands. They record the Geant4 reference physics list
with `/atris/physicsList`, the named output mode with `/atris/outputMode`, and
the Geant4 analysis format with `/atris/outputFormat`. Each source histogram
records its positive azimuth- and cosine-bin counts with separate properties
under `/atris/directionHistogram/` or `/atris/positionHistogram/`. The macro
then initializes the run,
selects a proton or alpha GPS source, records its minimum and maximum energy,
and selects the `Pow` distribution with index `-1`. It emits one primary per
event from a spherical surface, uses a cosine angular distribution over 0–90
degrees, sets a 100 m production cut, sets two random seeds with
`/atris/randomSeeds`, and issues one `/run/beamOn` command.

Despite its option name, `--particles-per-bin` is multiplied by the number of
**output-bin edges**, not the number of intervals:

$$
N_p=n m,\qquad N_\alpha=\lfloor nf_\alpha\rfloor m.
$$

Here $n$ is `particles_per_bin`, $m$ is `energy_points` (the number of
output-bin edges), and
$f_\alpha$ is `alpha_factor`; the floor represents integer truncation for
nonnegative counts.

The default totals are 363000 protons and 239580 alphas. The continuous
log-uniform source gives every logarithmic output interval the same expected
sampling probability. Actual sampled counts fluctuate and are recorded in the
primary histogram for normalization.

The current generator does not read `.spec` files or fold a physical primary
spectrum into the results. Such files may be retained as run inputs by
`atris-clone`, but do not control this generated simulation workflow.

## Phantom selection

`phantoms.txt` has three whitespace-separated fields per non-comment line:

```text
# stem                          mass_g      area_cm2
ramona_zero_0.060MeV_detA          0.5082      6.928
icru_zero_0.000MeV_detAB       14094.7550   1413.720
```

The stem identifies the phantom in macros and output filenames. Mass is in
grams and area in cm². Use the area associated with the response table's
calibration. The parser accepts
numeric mass and area values without checking that they are positive;
post-processing requires physically valid values.

The C++ executable does not read the mass or area. These values do not affect
Geant4 transport or the raw phantom histograms. `atris-postprocess` reads them
from `phantoms.txt` and applies the mass and area factors when producing
`.<stem>.dose`, `.<stem>.equi`, and `.<stem>.rates`; see the
[normalization formulas](outputs.md#processed-response-tables).

For each stem, staging locates `<stem>_response.txt` and `<stem>_counting.txt`
in the run directory first, then the archive. It creates relative symbolic links
under those descriptive names, or local files when `--copy` is used. Absolute
stems are supported. A missing `phantoms.txt` means an empty selection in the
Python tools. The executable does not read `phantoms.txt`; generated species
macros name each staged response and counting table explicitly.

## Phantom response matrices

Each table starts with an uncommented, whitespace-separated list of integer
PDG particle codes. Every subsequent particle row contains 650 coefficients,
in the same particle order as the header. All loaded response tables must have
identical PDG headers. The executable expects
`650 × number_of_PDG_codes` numeric values per table; a wrong count is reported
and stops execution.

The fixed energy edges are `10**linspace(-6, 7, 651)` MeV: 1 eV to 10 TeV,
with 0.02 spacing in log10 energy. The lookup uses
`max(0, int(log10(kinetic_energy/eV) / 0.02))`, without interpolation or an
upper-bound clamp. Keep energies inside the represented range.

The macro assigns each table one of three accumulation modes: `coefficient`
accumulates the table value directly, `energy` also multiplies by crossing
kinetic energy in eV, and `radiation-weighted-energy` additionally applies the
implemented radiation weight. See the
[normalization formulas](outputs.md#processed-response-tables). A dummy counting
table created with `--accept-missing-counting` contains ones and represents
unit counting response, not a measured efficiency.

Implementation: `atris_tools/psf.py`, `nrlmsis2psf.py`, `psf2gdml.py`,
`atrismacrogen.py`, `phantoms.py`, `src/RunConfiguration.cc`, and
`src/PhantomResponses.cc`.
