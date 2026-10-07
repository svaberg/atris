"""Small unit conversions used when reading AtRIS input files."""


ENERGY_TO_MEV = {
    "eV": 1.0e-6,
    "keV": 1.0e-3,
    "MeV": 1.0,
    "GeV": 1.0e3,
    "TeV": 1.0e6,
}


def energy_to_mev(value, unit):
    """Convert an energy value with a Geant4 unit name to MeV."""
    try:
        factor = ENERGY_TO_MEV[unit]
    except KeyError as error:
        raise ValueError("Unsupported energy unit: " + unit) from error
    return float(value) * factor
