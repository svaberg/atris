# Ionization, dose, and detector response

AtRIS produces several kinds of response. They describe different physical
quantities and require different normalization. A filename alone does not mean
that a result is already a physical dose or a rate per second.

## Ionizing energy deposition

The ionization tally accumulates total deposited energy minus non-ionizing
deposition in each sensitive layer. After post-processing, `.ioni` contains
ionizing energy deposition per unit volume per simulated primary, resolved by
primary-energy bin. Its units are MeV cm$^{-3}$ primary$^{-1}$.

This is not yet the number of ion pairs produced. Given an appropriate mean
energy $W$ required to form one ion pair, an estimate is

$$
N_{\mathrm{pairs}}=\frac{E_{\mathrm{ion}}}{W}.
$$

Use consistent energy units. The choice of $W$ depends on the material and
physical assumptions; AtRIS does not supply a universal value. A production
rate additionally requires an incident particle rate.

## Total atmospheric energy deposition

The total-deposition tally accumulates Geant4's total local energy deposit for
the same steps as the ionization tally. After post-processing, `.edep` contains
total deposited energy per unit volume per simulated primary, resolved by
primary-energy bin, in MeV cm$^{-3}$ primary$^{-1}$.

The difference `.edep - .ioni` is the correspondingly normalized non-ionizing
energy deposition. `.edep` is useful input to an atmospheric-heating estimate,
but it is not itself a heating rate: a physical incident spectrum and rate must
be applied, and converting deposited energy to heat requires an explicit
thermalization-efficiency assumption.

## Phantom responses

A phantom represents a detector or material with a particular geometry and
shielding. AtRIS uses precomputed response tables for particles crossing layer
interfaces; selecting a table does not insert a physical detector into the
planetary geometry or alter the surrounding particle transport. Choose a table
that represents the material and detector response you want to study. The
[phantom library](../reference/phantom-library.md) describes the supplied examples.

## Absorbed dose

Absorbed dose is energy deposited per unit mass:

$$
D=\frac{E_{\mathrm{dep}}}{m},\qquad 1\ \mathrm{Gy}=1\ \mathrm{J\,kg^{-1}}.
$$

AtRIS's phantom dose response is calculated from particles crossing an
interface and the selected phantom's response table. It is distinct from the
energy deposited directly in an atmospheric shell. The post-processor applies
primary-count, phantom-mass, and area normalization, but does not convert the
result to gray or apply a physical source flux. If a table uses dimensionless
energy fractions, its processed energy-per-mass response is in eV g$^{-1}$
per primary. Check the table's normalization before converting units.

The phantom lookup-table approach is described by
[Banjac et al. (2019)](https://doi.org/10.1029/2019JA026622).
It lets AtRIS evaluate a phantom's response to the transported particle field
without placing that phantom at every atmospheric level. The selected table
therefore determines which material and detector response the result describes.

## Radiation-weighted response

The `.<stem>.equi` output applies the radiation weights implemented in AtRIS to
the phantom response. It is intended to distinguish radiation types, rather than
treat equal deposited energies as interchangeable. It is not effective dose,
which requires tissue weighting and an appropriate anatomical model.

For interpretation, use the [implemented weighting formula](../reference/outputs.md#radiation-weighting-as-implemented).
That reference documents the code literally; do not assume the implementation
matches a radiation-protection standard solely from the output's name.

## Counts and count rates

The counting table supplies the detector response for a crossing particle.
The processed `.<stem>.rates` output is a response per primary, not counts per second.
A rate requires combining it with a physical incident source rate, using a
consistent source area and angular distribution. The same simulated particle
field can give different detector responses for different phantom tables.

See [processed output units](../reference/outputs.md#processed-response-tables)
and [source normalization](normalization-and-uncertainty.md) before applying
results to a physical irradiation scenario.

## Implementation

`src/SensitiveDetector.cc` implements the tallies and radiation weights;
`atris_tools/postprocess.py` implements the output normalization.
