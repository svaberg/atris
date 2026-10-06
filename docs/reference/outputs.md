# Output files

`<name>` below is the suffix-free simulation prefix. `<stem>` and `<response>`
are the names supplied by `/atris/phantom/response`. The simulation argument's
extension selects the Geant4 output backend independently of the output mode
and must match the macro's
`/atris/outputFormat` value. Without an extension, the macro value selects the
backend.

## Raw histogram files

| CSV suffix / ROOT object | Axes | Accumulated weight |
| --- | --- | --- |
| `_h1_h1.1.csv` / `h1.1` | Primary kinetic energy, MeV | Primary kinetic energy, MeV. Use `entries`, not `Sw`, for primary counts. |
| `_h2_h2.dir.csv` / `h2.dir` | Global azimuth, rad; cos(polar angle) | One per primary direction. |
| `_h2_h2.pos.csv` / `h2.pos` | Global azimuth, rad; cos(polar angle) | One per primary source position. |
| `_h2_h2.ion.csv` / `h2.ion` | Primary energy, MeV; detector ID | Total deposit minus non-ionizing deposit, MeV, for steps in non-terminating sensitive layers. |
| `_h2_h2.edep.csv` / `h2.edep` | Primary energy, MeV; detector ID | Total local energy deposit, MeV, for the same steps and layers as `h2.ion`. |
| `_h2_h2.<stem>.<response>.csv` / `h2.<stem>.<response>` | Primary energy, MeV; interface ID | The weight selected by the response's accumulation mode. |

All three modes write these histograms. CSV output writes one file per
histogram; ROOT output stores them as objects in `<name>.root`. There are
$5 + N_{\mathrm{response}}$ histogram products, where
$N_{\mathrm{response}}$ is the number of declared phantom responses. Despite
the histogram titles, raw phantom values have not yet been divided by primary
counts, masses, or interface areas.

The standard generated macros declare `dos`, `equi`, and `rates` responses.
Other response names are valid raw histograms; `atris-postprocess` only assigns
its established mass/area scaling to those three standard names.

By default, source-position and direction histograms have 120 azimuth bins from
0 to $2\pi$ and 60 $\cos\theta$ bins from -1 to 1. Their separate dimensions
are recorded in the species macro and may differ. Read the axes from the output
when analyzing an existing run.

### CSV structure

Files begin with `#` metadata lines, followed by a column header and numeric
rows. Axes are described by `#axis edges ...` or `#axis fixed N low high`.
AtRIS adds native Geant4 `#annotation` records identifying the histogram,
quantity, accumulated weight, simulation input prefix, physics list, output
mode, phantom count, software version, and random seed pair. Phantom-response
histograms also record their phantom stem, response name, source file, and
accumulation mode. A gathered histogram records the number of represented
chunks and all known seed pairs. Other provenance values that
differ between compatible chunks are retained with ` | ` separators; they do
not by themselves prevent gathering.

| Column | Meaning for a histogram fill with weight `w` |
| --- | --- |
| `entries` | Number of fills, independent of weight. |
| `Sw` | Sum of `w`. |
| `Sw2` | Sum of `w²`. |
| `Sxw0`, `Sx2w0` | Sum of `x*w` and `x²*w` for axis 0. |
| `Sxw1`, `Sx2w1` | Corresponding moments for axis 1, in H2 files. |

These are statistical accumulators, not one particle per CSV row. `Sw2` is not
a ready-to-use uncertainty on the final normalized result. `#planes_Sxyw` is
additional H2 cross-moment metadata; gather sums it with the other accumulators.

Underflow and overflow bins are included. For an energy-versus-detector H2
with `D` detector bins and `B` energy bins, the post-processor reshapes `Sw` to
`(D+2, B+2)`: energy varies fastest. Slicing `[1:-1, 1:-1]` removes the
underflow/overflow rows and columns. The raw primary H1 similarly contains
`B+2` rows. Header length varies with the available annotations, so readers
locate the first non-comment line rather than assuming a fixed line count.

### Detector and interface IDs

Ionization and total energy deposition are associated with the sensitive
volume's detector ID. Phantom responses and ROOT interface crossings use the
interface ID:

$$
\alpha = \arccos(\hat{\mathbf r}\cdot\hat{\mathbf p}),\qquad
\mathrm{interface\_id} =
\begin{cases}
\mathrm{detector\_id}-1, & \alpha < \pi/2,\\
\mathrm{detector\_id}, & \text{otherwise}.
\end{cases}
$$

Here $\hat{\mathbf r}$ is the radial unit position and $\hat{\mathbf p}$ is
the momentum direction.

The angle is measured from the outward local radial direction: outward-moving
particles have angles below 90 degrees, inward-moving particles above 90.
The recorded angle is rounded to the nearest whole degree, so a stored value of
90 cannot resolve a near-tangential crossing's original direction.

## Processed response tables

`atris-postprocess` writes headerless, whitespace-separated files:

| Suffix | Quantity after scaling |
| --- | --- |
| `.ioni` | Ionizing energy deposition per cm³ per primary in the corresponding energy bin, in MeV cm⁻³ primary⁻¹. It is not yet an ion-pair production rate. |
| `.edep` | Total local energy deposition per cm³ per primary in the corresponding energy bin, in MeV cm⁻³ primary⁻¹. It is not yet a heating rate. |
| `.<stem>.dose` | Phantom energy response per mass per primary, using the table's radiation coefficients and eV energy factor. |
| `.<stem>.equi` | The same response with the code's radiation weighting applied. |
| `.<stem>.rates` | Counting response per primary, after area scaling. It is not counts per second. |

Each row contains:

```text
detector_or_interface_id  altitude_km  response_bin_0  response_bin_1 ...
```

There is one response column for each interior primary-energy bin, in the
order recorded by the primary-energy histogram. No division by energy-bin width is
performed. IDs and altitudes are written with integer and three-decimal-place
formats respectively; response values use scientific notation with five
places after the decimal. The first and last physical layer rows are omitted.

Let $P_b$ be the primary H1 `entries` in energy bin $b$, $V_d$ the layer volume
in cm³, $S_d$ the interface area in cm², and $A_s$, $M_s$ the area and mass for
phantom stem $s$ from `phantoms.txt`. With raw ionizing and total-deposition
sums $I$ and $T$, and phantom sums $D$, $E$, and $C$:

$$
\begin{aligned}
\mathrm{ioni}_{d,b} &= \frac{I_{d,b}}{P_b V_d},\\
\mathrm{edep}_{d,b} &= \frac{T_{d,b}}{P_b V_d},\\
\mathrm{dose}_{s,d,b} &= \frac{D_{d,b} A_s}{P_b M_s S_d},\\
\mathrm{equi}_{s,d,b} &= \frac{E_{d,b} A_s}{P_b M_s S_d},\\
\mathrm{rates}_{s,d,b} &= \frac{C_{d,b} A_s}{P_b S_d}.
\end{aligned}
$$

Because `h2.ion` is total deposit minus Geant4's non-ionizing energy deposit,
`.edep - .ioni` gives the correspondingly normalized non-ionizing component.
Estimating atmospheric heating still requires a physical incident spectrum and
an assumption about how much deposited energy thermalizes as heat.

The code does not convert eV/g to Gy or apply a source flux or an ion-pair
creation energy. If the supplied radiation coefficients are dimensionless
energy fractions, `.<stem>.dose` has units eV g⁻¹ primary⁻¹; the conversion to
Gy primary⁻¹ would multiply by `1.602176634e-16`. The equivalent response has
the corresponding radiation-weighted units. Coefficient normalization and the
phantom's associated mass/area must be checked against that table's provenance;
the file format alone does not certify them.

An empty primary bin can yield NaN or infinity during division. The
post-processor does not fill unsampled bins or propagate uncertainties. It
warns about detectable input/output mismatches but does not generally reject
them. Keep the input geometry and phantom metadata with each run.

### Geometry and altitude

For PSF radii converted to cm, the post-processor calculates:

$$
\begin{aligned}
\Omega &= (\phi_{\mathrm{end}}-\phi_{\mathrm{start}})
 (\cos\theta_{\mathrm{start}}-\cos\theta_{\mathrm{end}}),\\
S_{\mathrm{inner}} &= \Omega r_{\mathrm{inner}}^2,\\
V &= \frac{\Omega}{3}(r_{\mathrm{outer}}^3-r_{\mathrm{inner}}^3).
\end{aligned}
$$

$\Omega$ is the angular factor.

For a zero-radius core, `S_inner` is replaced with its outer area. Rows are
stably sorted by this area. Reported altitude is
given in km by

$$
h_d = \frac{1}{10^5}\left(\sqrt{\frac{S_d}{4\pi}}-
\sqrt{\frac{S_2}{4\pi}}\right),
$$

where $S_2$ is the area at sorted row index 2.
The standard Earth layout makes this the inner-boundary altitude relative to
the first atmospheric layer. This altitude formula assumes full spherical
shells and the standard interior/crust/atmosphere row arrangement; it is not a
general altitude definition for arbitrary PSF sectors or layer orderings.

### Radiation weighting as implemented

The equivalent-response histogram uses weight 1 by default, 2 for absolute
PDG codes `2212` and `111`, and 20 for supported positive heavy-ion codes in
the phantom header. Thus the pion condition here specifically names neutral
pions; it is not a test for every pion species.

For neutrons, with $e$ equal to kinetic energy in MeV, the implemented weight is:

$$
w(e)=\begin{cases}
3.5+18.2\exp\!\left[-\frac{\ln(e^2)}{6}\right], & e\leq 1,\\
5.0+17.0\exp\!\left[-\frac{\ln((2e)^2)}{6}\right], & 1<e\leq 50,\\
2.5+3.25\exp\!\left[-\frac{\ln((0.04e)^2)}{6}\right], & e>50.
\end{cases}
$$

Here $\ln$ is the natural logarithm. These expressions describe the source
literally, including the placement of the square inside the logarithm; they
are not a statement that the implementation matches a particular radiation
protection standard.

(root-output)=

## ROOT output: `<name>.root`

When the simulation argument ends in `.root`, Geant4 writes one ROOT file. It
contains the response histograms listed above and, in modes `0` and `1`, a
`metadata` ntuple and the particle ntuples selected by the mode. AtRIS and its
Python tools use Uproot, so reading these products does not require a separate
ROOT installation.

The `metadata` ntuple contains one row for an ordinary run or one row per
represented chunk in a gathered ROOT file:

| Field | Meaning |
| --- | --- |
| `schema` | AtRIS metadata schema version. |
| `atris_version` | Version compiled into the executable. |
| `input_prefix` | Species input prefix used for geometry, macro, and bins. |
| `physics_list` | Geant4 reference physics list. |
| `output_mode` | Numeric AtRIS output mode. |
| `phantom_count` | Number of distinct phantom stems with loaded responses. |
| `seeds_explicit` | `1` when the output prefix supplied explicit chunk seeds. |
| `random_seed_1`, `random_seed_2` | The two explicit seeds, or zero for runtime defaults. |

Gather concatenates available metadata rows without using them as histogram
compatibility constraints. It combines only response histograms; the large
particle ntuples remain in the individual chunk files.

### Interface ntuple: `interfaces`

Written in modes `0` and `1` on entry into non-terminating sensitive volumes
when the pre-step status is a geometry boundary. A particle may cross many
interfaces or revisit one, so records are crossings, not unique particles.

| Field | Meaning |
| --- | --- |
| `pdg` | Particle PDG code. |
| `interface_id` | Interface ID. |
| `angle_degrees` | Rounded angle from the outward radius, degrees. |
| `kinetic_energy_MeV` | Pre-step particle kinetic energy, MeV. |
| `primary_energy_MeV` | Source primary kinetic energy, MeV. |

Records have no event or track identifier, and multithreaded output does not
define a global crossing order.

### Step ntuple: `steps`

Written in mode `1`, one row per processed step in a sensitive volume,
including terminating volumes.

| Field(s) | Meaning |
| --- | --- |
| `event_id` | Geant4 event ID; fallback `-1` if unavailable. |
| `track_id`, `parent_id` | Event-local track ID and parent track ID. |
| `step_id` | Current track step number. |
| `pdg` | Particle PDG code. |
| `detector_id` | Sensitive-volume ID. |
| `pre_x_km`, `pre_y_km`, `pre_z_km` | Pre-step Cartesian position, km. |
| `post_x_km`, `post_y_km`, `post_z_km` | Post-step Cartesian position, km. |
| `pre_kinetic_energy_MeV`, `post_kinetic_energy_MeV` | Kinetic energy at each endpoint. |
| `energy_deposit_MeV` | Total step energy deposit. |
| `nonionizing_energy_deposit_MeV` | Non-ionizing component of that deposit. |
| `step_length_m` | Step length, m. |
| `global_time_ns` | Post-step global time, ns. |
| `primary_energy_MeV` | Source primary kinetic energy, MeV. |
| `creator_process` | Process that created the track; `primary` for primary tracks. |
| `step_process` | Step-defining process; `none` if unavailable. |

Identify a track by event and track ID together. Across chunks, also retain the
chunk identity. Stream either ntuple as CSV without changing the ROOT file:

```bash
atris-dump protons.root interfaces | head
atris-dump protons.root steps | head
```

## Plots and chunk metadata

`atris-plot` replaces generated PNGs for the input/output groups available:

| Filename | Contents |
| --- | --- |
| `<species>.inputs.png` | Source and geometry inputs |
| `phantom.<name>.inputs.png` | Phantom input response curves, with a sanitized name |
| `<species>.png` | Source diagnostics and processed ionization |
| `<species>.<phantom-stem>.png` | Processed phantom responses |
| `<species>.interfaces.png` | Interface-crossing diagnostics |
| `<species>.steps.png`, `<species>.shower.png` | Step summary and shower visualization |
| `<species>.convergence.png` | Gathered ionization convergence diagnostics |

An unnamed phantom input plot uses `phantom-N.inputs.png`. The plot command
inspects canonical `protons` and `alphas` products in the selected directory;
it does not automatically collect per-chunk particle ntuples. See
[Scatter/gather files](chunks.md) for logs, completion markers, gathered-state
files, and the convergence CSV schema.

Implementation: `src/PrimaryGeneratorAction.cc`, `src/HistoManager.cc`,
`src/SensitiveDetector.cc`, `include/NtupleSchema.hh`, and
`atris_tools/postprocess.py`, `response_histograms.py`, `root_output.py`,
`interface_output.py`, `step_output.py`, and `plotting.py`.
