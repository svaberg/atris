"""Read and write AtRIS Planet Specification Format files."""

from pathlib import Path
from dataclasses import dataclass
import re

import numpy as np

# Fixed, zero-based columns in the PSF file format.
INNER_RADIUS = 0
OUTER_RADIUS = 1
PHI_START = 2
PHI_END = 3
THETA_START = 4
THETA_END = 5
DETECTOR_ID = 6
TEMPERATURE = 7
DENSITY = 8
PRESSURE = 9
STATE = 10
FIRST_ELEMENT = 11

GEOMETRY_COLUMNS = (
    INNER_RADIUS,
    OUTER_RADIUS,
    PHI_START,
    PHI_END,
    THETA_START,
    THETA_END,
)


@dataclass
class PSF:
    """A numeric layer table together with its ordered material definition."""

    layers: np.ndarray
    materials: str

    def formats(self, value_format):
        """Return NumPy formats preserving geometry and integer columns."""
        formats = [value_format] * self.layers.shape[1]
        for column in GEOMETRY_COLUMNS:
            formats[column] = "%s"
        formats[DETECTOR_ID] = formats[STATE] = "%d"
        return formats


def build_psf(
    *,
    inner_radius_km,
    outer_radius_km,
    temperature_k,
    density_g_cm3,
    pressure_pa,
    mass_fractions,
    solid_composition,
    state="gas",
):
    """Assemble full spherical shells from named physical quantities.

    Radii are one-dimensional arrays, ordered from the centre outwards.
    Other quantities accept a scalar or one value per layer. ``mass_fractions``
    maps element symbols to their scalar or per-layer mass fractions; its order
    determines both the numeric columns and the material header. Fractions must
    sum to one, except that solid layers may use all zeros to select
    ``solid_composition`` (a compact formula such as ``O533Si467``).

    ``state`` accepts ``gas``, ``solid``, or ``liquid``, individually or per layer.
    Detector IDs are assigned sequentially from zero. No interior, crust, or
    stopping shell is added implicitly; include them in the supplied arrays.
    The returned PSF can be passed directly to ``write_psf``.
    """
    inner = np.atleast_1d(np.asarray(inner_radius_km, dtype=float))
    outer = np.atleast_1d(np.asarray(outer_radius_km, dtype=float))
    if inner.ndim != 1 or inner.size == 0 or outer.shape != inner.shape:
        raise ValueError(
            "Inner and outer radii must be nonempty arrays of equal length"
        )
    if not np.isfinite(inner).all() or not np.isfinite(outer).all():
        raise ValueError("Radii must be finite")
    if np.any(inner < 0) or np.any(outer <= inner) or np.any(inner[1:] < outer[:-1]):
        raise ValueError(
            "Shells must have positive thickness and be ordered without overlap"
        )

    def per_layer(value, name, dtype=float):
        try:
            return np.broadcast_to(np.asarray(value, dtype=dtype), inner.shape)
        except (ValueError, TypeError) as error:
            raise ValueError(
                name + " must be a scalar or one value per layer"
            ) from error

    states = per_layer(state, "state", dtype=str)
    if not np.isin(states, ["gas", "solid", "liquid"]).all():
        raise ValueError("State must be gas, solid, or liquid")
    elements = list(mass_fractions)
    if not elements or any(
        not isinstance(e, str) or not re.fullmatch(r"[A-Z][a-z]?", e) for e in elements
    ):
        raise ValueError(
            "Mass fractions must be keyed by element symbols, e.g. N, C, O"
        )
    _compact_fractions(solid_composition)
    fractions = np.column_stack(
        [
            per_layer(mass_fractions[element], element + " mass fraction")
            for element in elements
        ]
    )
    if not np.isfinite(fractions).all() or np.any(fractions < 0):
        raise ValueError("Mass fractions must be finite and nonnegative")
    totals = fractions.sum(axis=1)
    fallback = (states == "solid") & (totals == 0)
    if not np.all(np.isclose(totals, 1, rtol=0, atol=1e-8) | fallback):
        raise ValueError(
            "Mass fractions must sum to one (or all zero for a compact solid)"
        )

    temperature = per_layer(temperature_k, "temperature_k")
    density = per_layer(density_g_cm3, "density_g_cm3")
    pressure = per_layer(pressure_pa, "pressure_pa")
    if not all(
        np.isfinite(values).all() for values in (temperature, density, pressure)
    ):
        raise ValueError("Temperature, density, and pressure must be finite")
    if np.any(temperature <= 0) or np.any(density <= 0) or np.any(pressure < 0):
        raise ValueError(
            "Temperature and density must be positive; pressure must be nonnegative"
        )

    layers = np.zeros((inner.size, FIRST_ELEMENT + len(elements)))
    layers[:, INNER_RADIUS], layers[:, OUTER_RADIUS] = inner, outer
    layers[:, PHI_END], layers[:, THETA_END] = 2 * np.pi, np.pi
    layers[:, DETECTOR_ID] = np.arange(inner.size)
    layers[:, TEMPERATURE], layers[:, DENSITY], layers[:, PRESSURE] = (
        temperature,
        density,
        pressure,
    )
    layers[:, STATE] = np.where(
        states == "solid", 1, np.where(states == "liquid", 2, 0)
    )
    layers[:, FIRST_ELEMENT:] = fractions
    return PSF(layers, " ".join([solid_composition, *elements]))


def write_psf(path, layers, *, materials=None, **kwargs):
    """Write a numeric layer array with column descriptions and material names.

    Pass the PSF returned by ``build_psf``, or a numeric array and a
    ``materials`` definition, e.g. ``"O533Si467 N"``.
    The array uses PSF units and column order, as returned by ``load_psf``.
    Additional keyword arguments are forwarded to ``numpy.savetxt``.
    Without ``fmt``, NumPy uses its own formatting. For column-specific
    formatting, pass e.g. ``fmt=psf.formats("%.3e")``.
    Existing files are replaced; the destination directory must already exist.
    This checks the table format, not the physical validity of the model.
    """
    if isinstance(layers, PSF):
        if materials is not None and materials != layers.materials:
            raise ValueError(
                "Material definition conflicts with the PSF's column order"
            )
        materials = layers.materials
        layers = layers.layers
    if materials is None:
        raise ValueError("A numeric layer array requires a material definition")
    fields = materials.split()
    if len(fields) < 2:
        raise ValueError("Specify a compact solid composition and material columns")
    _compact_fractions(fields[0])
    data = np.asarray(layers, dtype=float)
    if (
        data.ndim != 2
        or data.shape[0] == 0
        or data.shape[1] != FIRST_ELEMENT + len(fields) - 1
    ):
        raise ValueError(
            "PSF table must have one row per layer and columns for each fixed field and element"
        )
    if not np.isfinite(data).all():
        raise ValueError("PSF values must be finite")
    if not np.equal(data[:, DETECTOR_ID], np.floor(data[:, DETECTOR_ID])).all():
        raise ValueError("PSF detector IDs must be integers")
    if not np.isin(data[:, STATE], [0, 1, 2]).all():
        raise ValueError(
            "PSF material states must be 0 (gas), 1 (solid), or 2 (liquid)"
        )

    header = (
        "# AtRIS Planet Specification Format (PSF)\n"
        "# Units: radii km; angles rad; temperature K; density g/cm3; pressure Pa.\n"
        "# Columns: r_inner r_outer phi_start phi_end theta_start theta_end "
        "detector_id temperature density pressure state " + " ".join(fields[1:]) + "\n"
        "# Material columns are mass fractions. State: 0 gas, 1 solid, 2 liquid.\n"
        "# All-zero solid fractions use the compact composition in the material definition:\n"
        + " ".join(fields)
    )
    np.savetxt(path, data, header=header, comments="", encoding="utf-8", **kwargs)


def _locate_table(path):
    legacy_header = None
    with Path(path).open() as psf_file:
        for line_number, line in enumerate(psf_file):
            text = line.strip()
            if not text:
                continue
            if text.startswith("#"):
                if legacy_header is None:
                    legacy_header = text[1:].split()
                continue

            fields = text.split()
            try:
                float(fields[0])
            except ValueError:
                return fields, line_number + 1
            return legacy_header, line_number

    raise ValueError("PSF file contains no numeric table: " + str(path))


def read_psf_header(path):
    """Return the material-definition fields preceding the numeric table."""
    header, _ = _locate_table(path)
    if header is None:
        raise ValueError("PSF file contains no material definition: " + str(path))
    return header


def load_psf(path):
    """Return the numeric PSF table, skipping its descriptive and material headers."""
    _, data_start = _locate_table(path)
    return np.atleast_2d(np.loadtxt(path, skiprows=data_start))


def _compact_fractions(formula):
    parts = re.findall(r"([A-Z][a-z]*)(\d+)", formula)
    if not parts or "".join(element + weight for element, weight in parts) != formula:
        raise ValueError("Invalid compact PSF material formula: " + formula)
    total = sum(float(weight) for _, weight in parts)
    if total == 0:
        raise ValueError("PSF material formula has zero total weight: " + formula)
    return {element: float(weight) / total for element, weight in parts}


def read_psf_layers(path):
    """Return PSF rows as plotting-ready spherical material layers."""
    header = read_psf_header(path)
    data = load_psf(path)
    expected_columns = FIRST_ELEMENT + len(header) - 1
    if data.shape[1] != expected_columns:
        raise ValueError(
            "%s has %i columns; expected %i from its material definition"
            % (Path(path).name, data.shape[1], expected_columns)
        )

    compact_fractions = _compact_fractions(header[0])
    material_names = header[1:]
    states = {0.0: "gas", 1.0: "solid", 2.0: "liquid"}
    layers = []
    for row in data:
        state = states.get(row[STATE], "gas")
        fractions = {
            name: fraction
            for name, fraction in zip(material_names, row[FIRST_ELEMENT:])
            if fraction != 0.0
        }
        if state == "solid" and not fractions:
            fractions = compact_fractions.copy()
        layers.append(
            {
                "rmin": row[INNER_RADIUS],
                "rmax": row[OUTER_RADIUS],
                "detector_id": int(row[DETECTOR_ID]),
                "temperature": row[TEMPERATURE],
                "density": row[DENSITY],
                "pressure": row[PRESSURE],
                "state": state,
                "fractions": fractions,
            }
        )
    return layers
