# Phantom library

The `phantoms/` directory contains precomputed response and counting tables.
Choose the phantom material, geometry, shielding, and threshold that match the
quantity you want to estimate. The tables describe a response to the transported
particle field; [phantom responses](../background/radiation-quantities.md#phantom-responses)
explains their physical role.

## Available example phantoms

The supplied Earth example selects these two table pairs:

| Table stem | Phantom |
| --- | --- |
| `ramona_zero_0.060MeV_detA` | RAMONA/DOSTEL silicon detector A, without added aluminium shielding, with the 0.060 MeV threshold |
| `icru_zero_0.000MeV_detAB` | A water sphere of radius 15 cm, without added aluminium shielding, with the 0.000 MeV threshold |

Both families also have response/counting pairs with the shielding labels
`five`, `ten`, `fifteen`, and `twenty` for 5, 10, 15, and 20 mm of aluminium.
RAMONA pairs are supplied for both `0.000MeV` and `0.060MeV` thresholds;
the ICRU pairs use `0.000MeV`. Other variants and historical files are also
present in the archive. Establish their geometry and normalization before
substituting them for the documented examples.

## Select and stage tables

The example selection file records the table stems and the mass and area used
for normalization:

```{literalinclude} ../../examples/earth-nrlmsis-full/phantoms.txt
:language: text
:caption: examples/earth-nrlmsis-full/phantoms.txt
```

To use this selection, work inside a prepared run directory:

```bash
cp "$ATRIS_ROOT/examples/earth-nrlmsis-full/phantoms.txt" .
atris-stage-phantoms . --copy
```

For your own selection, edit `phantoms.txt` before staging. Each stem identifies
`<stem>_response.txt` and `<stem>_counting.txt`; row order assigns the phantom
IDs. The staging command places those named files in the run directory. See
[phantom selection](inputs.md#phantom-selection) for row order and metadata,
[response-matrix format](inputs.md#phantom-response-matrices) for the table
layout and fixed energy grid, and [atris-stage-phantoms](commands/atris-stage-phantoms.md)
for archive paths and staging options.

Phantoms are optional. A run without them still records atmospheric ionizing
energy deposition.

## Historical update: autumn 2021

The following notes by Saša Banjac document the library's development. Claims
about branches, removals, and planned tables describe that period. For current
file requirements and staging, use the references above.

* AtRIS now also simulates count rates using an advanced counting efficiency response matrix
   - The new phantom generation routines create this matrix
   - A separate branch of AtRIS has been created for the binary output required for the phantoms
   - Previous phantoms are removed. From now on, only ICRU sphere and a ramona phantom is available
   - 5 versions of the RAMONA DOSTEL phantom are created with various shielding thicknesses:
     0 mm Aluminium, 5 mm, 10 mm, 15 mm, 20 mm.
   - For the ICRU sphere, a similar set of shielded phantoms is being created.
   - Counting response matrices have the same phantom name, but the suffix "_counting" is expected
   - If a counting response matrix is not available, use ideal_counting_response.txt from the files directory
   - We now use only extended phantoms that consider also GCR nuclei

### Extended phantoms (historical notes)
These phantoms include response to GCR fully ionized nuclei from Z=3 to Z=28 (most abundant isotope).
For water, I've used .997 g per ccm as desnity, while for TEM it is 1.00 g per ccm

 * icru_b phantom is a r=15cm sphere of water
   -                shape: solid sphere
   -          composition: h2o
   -               radius: 15 cm
   -                 mass: 14094.7550 g
   -                 area: 1413.72 cm2
 * ramona phantom is a phantom corresponds to the RAMONA/DOSTEL detector A with aluminum shielding in front
   -                shape: disc
   -          composition: Si
   -               radius: 14.85 mm
   -            thickness: 0.315 mm
   -                 mass: 0.5082 g
   -                 area: 6.928 cm2

## Archived exploration notebook

[View notebook](notebooks/explorer_v2.ipynb) to read the original phantom
exploration code and saved outputs, or download
{download}`explorer_v2.ipynb <notebooks/explorer_v2.ipynb>` to work locally.
The Jupyter notebook is located at `docs/reference/notebooks/explorer_v2.ipynb`
in the project. This is an archived
development notebook, not an automatically executed tutorial.

It uses NumPy, Matplotlib, and pandas, reads response, variance, and counting
tables from the kernel's working directory, and expects `../phantom.bins`.
That bin file is not provided at that path in this checkout. Before running,
configure the working directory and supply or update the bin-file path. The
code also writes PDF plots to its working directory. The original notebook is
preserved without changing its analysis.

```{toctree}
:hidden:

notebooks/explorer_v2
```
