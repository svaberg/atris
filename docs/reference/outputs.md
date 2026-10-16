# Output files

`<name>` below is the suffix-free simulation prefix; `N` is a zero-based
phantom ID. The simulation argument's extension selects the Geant4 output
backend independently of the output mode. A missing extension defaults to CSV.
The internal phantom-statistics mode (`3`) instead defaults to ROOT.

## Raw histogram files

| CSV suffix / ROOT object | Axes | Accumulated weight |
| --- | --- | --- |
| `_h1_h1.1.csv` / `h1.1` | Primary kinetic energy, MeV | One per primary. Use `entries` in CSV or bin contents in ROOT for primary counts. |
| `_h2_h2.dir.csv` / `h2.dir` | Global azimuth, rad; cos(polar angle) | One per primary direction. |
| `_h2_h2.pos.csv` / `h2.pos` | Global azimuth, rad; cos(polar angle) | One per primary source position. |
| `_h2_h2.ion.csv` / `h2.ion` | Primary energy, MeV; detector ID | Total deposit minus non-ionizing deposit, MeV, for steps in non-terminating sensitive layers. |
| `_h2_h2.edep.csv` / `h2.edep` | Primary energy, MeV; detector ID | Total local energy deposit, MeV, for the same steps and layers as `h2.ion`. |
| `_h2_h2.dosN.csv` / `h2.dosN` | Primary energy, MeV; interface ID | Radiation response coefficient × crossing kinetic energy in eV. |
| `_h2_h2.equiN.csv` / `h2.equiN` | Primary energy, MeV; interface ID | The same energy response multiplied by the implemented radiation weight. |
| `_h2_h2.ratesN.csv` / `h2.ratesN` | Primary energy, MeV; interface ID | Counting response coefficient. |

All output modes write these histograms, plus the per-primary companions below.
CSV output writes one file per histogram; ROOT output stores them as objects in
`<name>.root`. Together there are $7 + 6N_{\mathrm{phantom}}$ histogram products,
where $N_{\mathrm{phantom}}$ is the phantom count (mode `3` adds two more).
Despite the histogram titles, raw
phantom values have not yet been divided by primary counts, masses, or interface
areas.

Source-position and direction histograms have 120 azimuth bins from 0 to $2\pi$
and 60 $\cos\theta$ bins from -1 to 1.

### Per-primary sampling uncertainty

Each response histogram (`h2.ion`, `h2.edep`, `h2.dosN`, `h2.equiN`, and
`h2.ratesN`) has a companion with `.primary` appended to its name. For example,
`h2.ion.primary` in ROOT is `<name>_h2_h2.ion.primary.csv` in CSV. These use the
same axes and units as the original histograms. Existing filenames, columns,
and statistics retain their meanings.

With one incoming primary per Geant4 event, AtRIS temporarily totals the contributions of all
its tracks to each response bin, including crossings of the same interface from
either side. At the end of the event it fills the companion with this total.
Only the accumulated histograms are saved, not individual-primary records.

For a given response bin, let $x_i$ be primary $i$'s total contribution. The
companion stores $S=\sum_i x_i$ in its bin contents and $Q=\sum_i x_i^2$ in
`Sw2` (CSV) or `fSumw2` (ROOT). Its contents therefore duplicate the original
sum, apart from floating-point summation order. The original squared sums still
refer to individual steps or crossings. The source histograms and the mode `3`
fraction and detection histograms do not need companions.

Use the corresponding `h1.1` bin for the primary count $N$, including primaries
that contribute zero. **Do not use the companion's fill count as $N$:** zero
contributions need no fill. With independent incoming primaries, the mean and
estimated variance of that mean are

$$
\bar{x}=\frac{S}{N},\qquad
\operatorname{Var}(\bar{x})=\frac{Q-S^2/N}{N(N-1)},\qquad N>1.
$$

`ResponseHistogramReader.mean_variance(name)` calculates this variance in raw
response units squared, returning an `(energy, layer)` array including flow
bins. It returns `NaN` where $N<2$ and raises an error if the companion is
missing. Small negative results from roundoff in moment subtraction are clipped
to zero. Native Geant4 CSV writes six significant digits. When subtraction
approaches that rounding limit, this method warns that small variances cannot
be resolved reliably; use ROOT for those estimates. The zero produced by
clipping is not evidence of exact zero variance. Older output cannot reconstruct
$Q$ from its per-fill squared sums.
Gathering adds the companion histograms just like the originals and rejects
chunks with differing histogram sets, including mixtures with and without
companions.

For deterministic normalization, multiply the variance by the square of the
factor applied to the mean. Folding independent primary-energy bins with fixed
weights $a_b$ gives variance $\sum_b a_b^2 V_b$, where $V_b$ is the per-primary
mean variance for energy bin $b$. This supplies pointwise Monte Carlo sampling
errors; it does not include phantom-table coefficient uncertainty or
covariances between output bins. Existing post-processed tables are unchanged.

Companions are native Geant4 histograms in both formats. In ROOT each adds a
contents array and a squared-sum array; this first implementation deliberately
keeps the duplicate contents rather than introducing a custom compact format.

### Phantom statistics

Internal mode `3` adds two energy-versus-detector histograms. For each primary,
the sensitive detector first totals ionizing deposition from the primary and
its secondaries; only then does it fill these histograms, including zero
deposits. Termination shells are not scored detector volumes.

| ROOT object | Per-bin quantity |
| --- | --- |
| `h1.1` | Primary count $N$ (unit-weight fills). |
| `h2.fraction` | Sum $S$ of ionizing deposited-energy fractions $x=E_{\mathrm{ion}}/E_{\mathrm{incident}}$, with squared sum $Q=\sum x^2$ in ROOT's `fSumw2`. |
| `h2.detected` | Count $K$ of primaries with strictly positive ionizing deposit. |

The response is $S/N$, counting efficiency is $K/N$, and the sampled variance
of individual energy fractions is $(Q-S^2/N)/(N-1)$ for $N>1$.
ROOT's squared sums are not themselves sample variances. Raw-moment subtraction
has floating-point cancellation when the variance is very small.

`read_phantom_statistics` in `atris_tools.phantom` reads these
statistics and also accepts older event-record chunks. `PhantomBuilder.gather()`
combines completed builder batches; `phantom.save()` writes the tables and sampling uncertainties.
New phantom-mode files contain histograms and run metadata, not per-primary,
interface-crossing, or transport-step records. The grid fixes their array sizes,
regardless of how many primaries a chunk simulates. Changing the zero counting
threshold afterward requires individual-event records and is not supported by
the compact files.

### CSV structure

Files begin with `#` metadata lines, followed by a column header and numeric
rows. Axes are described by `#axis edges ...` or `#axis fixed N low high`.
Read the axes from the output when analyzing an existing run.

AtRIS adds native Geant4 `#annotation` records identifying the histogram,
quantity, accumulated weight, simulation input prefix, physics list, output
mode, phantom count, software version, and random seed pair. Phantom-response
histograms also record the phantom ID. A gathered histogram records the number
of represented chunks and all known seed pairs. Other provenance values that
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

## Phantom sampling ROOT exports

`Phantom.save` writes `<name>_sampling.root` alongside the response
and counting text tables. `Phantom.read_root` restores the scientific
arrays and metadata without reading the text tables or runner JSON files.

The `sampling` TTree has one entry per species, in response-table order:

| Branch | Type and meaning |
| --- | --- |
| `pdg_codes` | Scalar int64 particle identifier. |
| `sample_counts`, `detected_counts` | 650 int64 values: primary counts and positive-ionizing-deposit counts. |
| `energy_fraction` | 650 float64 values: mean ionizing deposited-energy fraction, including zero-deposit primaries. |
| `counting_efficiency` | 650 float64 values: detected count divided by primary count. |
| `fraction_variance`, `counting_variance` | 650 float64 values: unbiased sample variances of individual fractions and detection indicators. |
| `fraction_standard_error`, `counting_standard_error` | 650 float64 values: standard errors of the corresponding means. |

The `energy_bins` TTree has 650 entries with float64 `lower_MeV` and
`upper_MeV` branches on the fixed AtRIS kinetic-energy grid. Fractions,
efficiencies, their variances, and their standard errors have no units.
Unsampled means and uncertainties are NaN; counts remain zero. A single sample
has a mean but no estimated variance or standard error.

The `metadata` TObjString contains JSON text recording geometry, normalization,
counting threshold, units, and generation provenance. `geometry_psf` contains
the actual PSF contents, including radii, angular extent, material fractions,
density, temperature, pressure, and their units. `geometry_psf_role` identifies
whether this is the `physical` input layer or the expanded `transport` geometry.
When no PSF was supplied to the response model, this field is null, not a
reconstructed geometry presented as an original input.

Metadata uses numeric values, booleans, short labels, and nested records rather
than explanatory paragraphs. `schema` is `atris.phantom.v1`. `source` records
the disk radius and centre in cm, direction vector, and energy sampling.
`incident_energy` is `total_kinetic_energy`, `normalization` is
`per_incident_primary`, `variance_ddof` is 1, and `uncertainty` is
`standard_error_of_mean`. `sampling_status` is `partial` if any bin is unsampled,
otherwise `sampled`; neither label establishes precision completion.

With ionizing deposit $W_{\mathrm{ion}}$ and incident kinetic energy $K$,
`response_definition` is `mean(W_ion/K)` and `counting_definition` is
`P(W_ion > threshold)`. Zero-deposit primaries are included in both estimates.
The counting threshold does not gate the energy response. Variances use
denominator $N-1$, and standard errors are $\sqrt{s^2/N}$. A zero estimated
counting error does not rule out rare events.

The `validity` object records spherical geometry, scoring and termination IDs,
and whether energy extrapolation is supported. The retained physical PSF records
the layers and their material settings.
The [water-sphere table](phantom-library.md#water-sphere-phantoms) gives the
key properties of the four phantom runs. In this transport geometry,
detector ID 1 scores the innermost physical layer. Outer physical layers are
passive shielding and have no sensitive detector attached. IDs 0 and 2 are vacuum termination
shells: deposits there do not contribute. These detector IDs are not the
phantom IDs assigned when loading tables into another atmospheric run. A
physical PSF may have different input detector IDs; transport assigns the scoring
ID to the innermost layer when adding termination shells.

The response applies to the recorded spherical layers and material settings.
Detector mass and density refer only to the innermost layer. The source disk
covers the outer radius of the full PSF, including shielding, and response means
include primaries that never reach the detector. The effective area is
$2\pi R_\mathrm{source}^2$, not the detector's projected area. The projected-disk
beam can represent incoming directions because of spherical symmetry. It does
not describe a different surrounding geometry or a nonspherical object. Only the stored PDG rows and
kinetic-energy bins are calibrated. Missing species are not zero responses,
and the file does not justify extrapolation beyond its grid. NaN estimates and
finite estimates with inadequate precision remain incomplete sampling results.
Builder exports record `precision_settings`: relative dose tolerance, absolute dose
tolerance in Gy, and confidence factor. Apply the
[builder's precision criterion](../running-atris/build-phantoms.md#refine-and-inspect)
to the retained means, errors, and counts. A response created without those
settings does not establish that any particular precision target was met.

The TXT tables project the response arrays and retain short interpretive headers;
they do not duplicate the full ROOT metadata. JSON files retain operational
build settings, batch history, and progress needed to extend or resume a run;
there is no separate response-metadata JSON export. Build and batch settings read
geometry directly from PSF; ROOT retains the PSF associated with the results.

## Processed response tables

`atris-postprocess` writes headerless, whitespace-separated files:

| Suffix | Quantity after scaling |
| --- | --- |
| `.ioni` | Ionizing energy deposition per cm³ per primary in the corresponding energy bin, in MeV cm⁻³ primary⁻¹. It is not yet an ion-pair production rate. |
| `.edep` | Total local energy deposition per cm³ per primary in the corresponding energy bin, in MeV cm⁻³ primary⁻¹. It is not yet a heating rate. |
| `.doseN` | Phantom energy response per mass per primary, using the table's radiation coefficients and eV energy factor. |
| `.equiN` | The same response with the code's radiation weighting applied. |
| `.ratesN` | Counting response per primary, after area scaling. It is not counts per second. |

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
in cm³, $S_d$ the interface area in cm², and $A_N$, $M_N$ the phantom area and
mass from `phantoms.txt`. With raw ionizing and total-deposition sums $I$ and
$T$, and phantom sums $D$, $E$, and $C$:

$$
\begin{aligned}
\mathrm{ioni}_{d,b} &= \frac{I_{d,b}}{P_b V_d},\\
\mathrm{edep}_{d,b} &= \frac{T_{d,b}}{P_b V_d},\\
\mathrm{dose}_{N,d,b} &= \frac{D_{d,b} A_N}{P_b M_N S_d},\\
\mathrm{equi}_{N,d,b} &= \frac{E_{d,b} A_N}{P_b M_N S_d},\\
\mathrm{rates}_{N,d,b} &= \frac{C_{d,b} A_N}{P_b S_d}.
\end{aligned}
$$

Because `h2.ion` is total deposit minus Geant4's non-ionizing energy deposit,
`.edep - .ioni` gives the correspondingly normalized non-ionizing component.
Estimating atmospheric heating still requires a physical incident spectrum and
an assumption about how much deposited energy thermalizes as heat.

The code does not convert eV/g to Gy or apply a source flux or an ion-pair
creation energy. With radiation tables containing the expected dimensionless
energy fractions, `.doseN` has units eV g⁻¹ primary⁻¹; the conversion to
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

The weight uses the crossing particle's species and kinetic energy, including
secondary particles. The histogram's energy axis instead records the initiating
primary's energy. The physical meaning and calculation sequence are explained
under [radiation-weighted response](../background/radiation-quantities.md#radiation-weighted-response).

For neutrons, with $e=E_{\mathrm{kin}}/(1\,\mathrm{MeV})$, the implemented weight is:

$$
w(e)=\begin{cases}
3.5+18.2\exp\!\left[-\frac{\ln(e^2)}{6}\right], & e\leq 1,\\
5.0+17.0\exp\!\left[-\frac{\ln((2e)^2)}{6}\right], & 1<e\leq 50,\\
2.5+3.25\exp\!\left[-\frac{\ln((0.04e)^2)}{6}\right], & e>50.
\end{cases}
$$

Here $\ln$ is the natural logarithm. The differences from ICRP Publication 103,
including the square inside the logarithm, are recorded as a
[possible radiation-weighting bug](../known-bugs.md#possible-radiation-weighting-bug).

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
| `phantom_count` | Number of loaded phantom pairs. |
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
| `phantom.<name>.inputs.png` | Counting efficiency and mean deposited-energy fraction, with constant deposited-energy guides and a sanitized phantom name |
| `<species>.png` | Source diagnostics and processed ionization |
| `<species>.<phantom-stem>.png` | Processed phantom responses |
| `<species>.interfaces.png` | Interface-crossing diagnostics |
| `<species>.steps.png`, `<species>.shower.png` | Step summary and shower visualization |
| `<species>.convergence.png` | Gathered ionization convergence diagnostics |

Unnamed phantom input plots use `phantom-N.inputs.png`. Each available response
table contributes one row to the combined image.
The old combined `phantom.<name>.inputs.png` is no longer generated; existing
copies are left untouched. The plot command
inspects canonical `protons` and `alphas` products in the selected directory;
it does not automatically collect per-chunk particle ntuples. See
[Scatter/gather files](chunks.md) for logs, completion markers, gathered-state
files, and the convergence CSV schema.

The Python `ResponseHistogramReader` returns a `Histogram` through
`histograms[name]` for both CSV and ROOT. Its `values` and `axes` arrays include
flow-bin values and ordinary bin edges respectively. `sumw2` contains the
recorded per-bin squared-weight sums, or `None` when unavailable; it is not the
standard error of a mean. ROOT labels and accumulated statistics, and CSV header
annotations, remain attached to the object. CSV primary values are entry counts,
so weighted-fill uncertainties are not assigned to those counts.
CSV gathering uses this same model. `bin_statistics` retains every recorded
column in axis order, with the columns identified by `columns`; `entries` exposes
the per-bin fill counts. These fields are unavailable in ROOT where they were
not recorded. Gathering adds compatible histogram statistics without inventing
missing moments or converting between the two formats.

Implementation: `src/PrimaryGeneratorAction.cc`, `src/HistoManager.cc`,
`src/SensitiveDetector.cc`, `src/EventAction.cc`, `include/NtupleSchema.hh`, and
`atris_tools/postprocess.py`, `histogram.py`, `root_records.py`, and `plotting.py`.
