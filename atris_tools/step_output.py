"""Read transport-step ntuples written by AtRIS output mode 1."""

from .root_output import iterate_ntuple

STEP_FIELDS = (
    "event_id",
    "track_id",
    "parent_id",
    "step_id",
    "pdg",
    "detector_id",
    "pre_x_km",
    "pre_y_km",
    "pre_z_km",
    "post_x_km",
    "post_y_km",
    "post_z_km",
    "pre_kinetic_energy_MeV",
    "post_kinetic_energy_MeV",
    "energy_deposit_MeV",
    "nonionizing_energy_deposit_MeV",
    "step_length_m",
    "global_time_ns",
    "primary_energy_MeV",
    "creator_process",
    "step_process",
)


def iterate_step_records(filename):
    """Yield bounded record arrays from one AtRIS mode-1 ROOT file."""
    return iterate_ntuple(filename, "steps", STEP_FIELDS)


def process_name(value):
    """Return a process name read from a ROOT string column."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
