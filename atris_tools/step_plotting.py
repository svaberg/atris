"""Plot transport-step traces written by AtRIS output mode 1."""

import random
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
import numpy as np

from .input_plotting import (
    mark_model_regions,
    model_shell_edges,
    particle_symbol,
    positive_log_edges,
    read_layers,
    setup_shell_axis,
    shell_coordinates,
    surface_radius,
)
from .step_output import iterate_step_records, process_name

ENERGY_SAMPLE_LIMIT = 100_000
BAR_LIMIT = 12
SHOWER_SPECIES_LIMIT = 6
INTERACTION_ALTITUDE_MARGIN = 0.05
MINIMUM_ALTITUDE_MARGIN_KM = 1.0


def read_step_trace(filename, sample_limit=ENERGY_SAMPLE_LIMIT):
    """Stream a mode-1 trace into aggregate counts and a bounded sample."""
    path = Path(filename)
    random_generator = random.Random(0)
    particle_counts = Counter()
    process_counts = Counter()
    event_counts = Counter()
    detector_counts = Counter()
    detector_deposit = defaultdict(float)
    energy_sample = []
    positive_energy_rows = 0
    row_count = 0
    first_event = None
    last_event = None

    for records in iterate_step_records(path):
        for row in records:
            event_id = int(row["event_id"])
            pdg = int(row["pdg"])
            detector_id = int(row["detector_id"])
            kinetic_energy = float(row["post_kinetic_energy_MeV"])
            energy_deposit = float(row["energy_deposit_MeV"])
            if not np.isfinite(kinetic_energy) or not np.isfinite(energy_deposit):
                raise ValueError(
                    "%s has non-finite numeric data in record %i"
                    % (path.name, row_count)
                )

            row_count += 1
            first_event = (
                event_id if first_event is None else min(first_event, event_id)
            )
            last_event = event_id if last_event is None else max(last_event, event_id)
            event_counts[event_id] += 1
            particle_counts[pdg] += 1
            process_counts[process_name(row["step_process"]) or "unknown"] += 1
            detector_counts[detector_id] += 1
            detector_deposit[detector_id] += energy_deposit

            if kinetic_energy <= 0 or sample_limit <= 0:
                continue
            positive_energy_rows += 1
            sample_row = (detector_id, kinetic_energy)
            if len(energy_sample) < sample_limit:
                energy_sample.append(sample_row)
                continue
            replacement = random_generator.randrange(positive_energy_rows)
            if replacement < sample_limit:
                energy_sample[replacement] = sample_row

    if not row_count:
        raise ValueError(path.name + " contains no step records")
    return {
        "path": path,
        "row_count": row_count,
        "first_event": first_event,
        "last_event": last_event,
        "event_counts": event_counts,
        "particle_counts": particle_counts,
        "process_counts": process_counts,
        "detector_counts": detector_counts,
        "detector_deposit": detector_deposit,
        "energy_sample": energy_sample,
        "positive_energy_rows": positive_energy_rows,
    }


def _plot_counts(axis, counts, title, xlabel, labels):
    most_common = counts.most_common(BAR_LIMIT)
    names = [labels(value) for value, _ in most_common]
    values = [count for _, count in most_common]
    omitted = sum(counts.values()) - sum(values)
    if omitted:
        names.append("other")
        values.append(omitted)
    axis.barh(names, values, color="#18788f")
    axis.invert_yaxis()
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_xscale("log")


def plot_step_trace(simname, summary):
    """Create a bounded-memory overview of an AtRIS mode-1 step trace."""
    detector_ids = sorted(summary["detector_counts"])
    geometry_path = Path(simname + ".gdml")
    layers = read_layers(geometry_path)
    model_edges = model_shell_edges(layers)

    figure, axes = plt.subplots(
        ncols=2, nrows=2, figsize=(13, 11), layout="constrained"
    )
    _plot_counts(
        axes[0, 0],
        summary["particle_counts"],
        "Particle species",
        "Recorded steps",
        lambda pdg: particle_symbol(int(pdg)),
    )
    _plot_counts(
        axes[0, 1],
        summary["process_counts"],
        "Step-defining processes",
        "Recorded steps",
        str,
    )

    development_axis = axes[1, 0]
    detector_ids, plot_positions, plot_edges = shell_coordinates(layers, detector_ids)
    counts = np.asarray([summary["detector_counts"][value] for value in detector_ids])
    deposits = np.asarray(
        [summary["detector_deposit"][value] for value in detector_ids]
    )
    positive_deposit = deposits > 0
    deposit_axis = development_axis.twiny() if np.any(positive_deposit) else None
    boundary_axis = deposit_axis if deposit_axis is not None else development_axis
    mark_model_regions(boundary_axis, model_edges)
    development_axis.plot(counts, plot_positions, color="#18788f", label="Steps")
    setup_shell_axis(development_axis)
    development_axis.set_xscale("log")
    development_axis.set_xlabel("Recorded steps", color="#18788f")
    development_axis.tick_params(axis="x", colors="#18788f")
    development_axis.set_title("Shower development")
    if deposit_axis is not None:
        deposit_axis.plot(
            deposits[positive_deposit],
            plot_positions[positive_deposit],
            color="#d2671f",
            label="Deposited energy",
        )
        deposit_axis.set_xscale("log")
        deposit_axis.set_xlabel("Deposited energy [MeV]", color="#d2671f")
        deposit_axis.tick_params(axis="x", colors="#d2671f")

    sample = [
        (detector_id, energy)
        for detector_id, energy in summary["energy_sample"]
        if detector_id in detector_ids
    ]
    energy_axis = axes[1, 1]
    mark_model_regions(energy_axis, model_edges)
    if sample:
        position_by_id = dict(zip(detector_ids, plot_positions))
        sample_positions = np.asarray(
            [position_by_id[detector_id] for detector_id, _ in sample]
        )
        sample_energies = np.asarray([energy for _, energy in sample])
        energy_edges = positive_log_edges(sample_energies)
        histogram, _, _ = np.histogram2d(
            sample_energies,
            sample_positions,
            bins=(energy_edges, plot_edges),
        )
        positive_counts = histogram[histogram > 0]
        color_norm = LogNorm(
            vmin=np.min(positive_counts),
            vmax=max(np.max(positive_counts), np.min(positive_counts) * 10),
        )
        mesh = energy_axis.pcolormesh(
            energy_edges,
            plot_edges,
            histogram.T,
            cmap="Blues",
            norm=color_norm,
            shading="flat",
            rasterized=True,
        )
        energy_axis.set_xscale("log")
        figure.colorbar(mesh, ax=energy_axis, label="Sampled steps")
    else:
        energy_axis.text(
            0.5,
            0.5,
            "No positive kinetic energies",
            ha="center",
            va="center",
            transform=energy_axis.transAxes,
        )
    setup_shell_axis(energy_axis)
    energy_axis.set_title("Kinetic energy through the shells")
    energy_axis.set_xlabel("Post-step kinetic energy [MeV]")

    event_range = "%i-%i" % (
        summary["first_event"],
        summary["last_event"],
    )
    sample_note = ""
    if summary["positive_energy_rows"] > len(summary["energy_sample"]):
        sample_note = "; energy panel samples %s rows" % format(
            len(summary["energy_sample"]), ","
        )
    figure.suptitle(
        "%s mode-1 step trace: %s rows, event IDs %s%s"
        % (
            simname.capitalize(),
            format(summary["row_count"], ","),
            event_range,
            sample_note,
        )
    )
    filename = simname + ".steps.png"
    figure.savefig(filename)
    plt.close(figure)
    return filename


def _read_event_steps(filename, event_id):
    segments = []
    particle_codes = []
    parent_ids = []
    step_processes = []
    track_ids = set()
    for records in iterate_step_records(filename):
        for row in records[records["event_id"] == event_id]:
            pre_position = [
                float(row["pre_x_km"]),
                float(row["pre_y_km"]),
                float(row["pre_z_km"]),
            ]
            post_position = [
                float(row["post_x_km"]),
                float(row["post_y_km"]),
                float(row["post_z_km"]),
            ]
            particle_codes.append(int(row["pdg"]))
            parent_ids.append(int(row["parent_id"]))
            step_processes.append(process_name(row["step_process"]))
            track_ids.add(int(row["track_id"]))
            segments.append((pre_position, post_position))
    if not segments:
        raise ValueError("Event %i has no recorded steps" % event_id)
    return (
        np.asarray(segments),
        np.asarray(particle_codes),
        np.asarray(parent_ids),
        np.asarray(step_processes),
        len(track_ids),
    )


def _local_shower_coordinates(segments):
    """Project global positions onto the initial primary's local frame."""
    origin = segments[0, 0]
    shower_axis = segments[0, 1] - origin
    if not np.any(shower_axis):
        shower_axis = segments[-1, 1] - origin
    shower_axis /= np.linalg.norm(shower_axis)

    reference_axis = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(shower_axis, reference_axis)) > 0.9:
        reference_axis = np.array([0.0, 1.0, 0.0])
    transverse_x = np.cross(shower_axis, reference_axis)
    transverse_x /= np.linalg.norm(transverse_x)
    transverse_y = np.cross(shower_axis, transverse_x)
    basis = np.column_stack((transverse_x, transverse_y, shower_axis))
    return (segments - origin) @ basis


def plot_shower(simname, summary):
    """Plot the mode-1 event with the largest number of recorded steps."""
    trace_path = Path(simname + ".root")
    event_id, step_count = summary["event_counts"].most_common(1)[0]
    (
        segments,
        particle_codes,
        parent_ids,
        step_processes,
        track_count,
    ) = _read_event_steps(trace_path, event_id)
    local_segments = _local_shower_coordinates(segments)
    layers = read_layers(simname + ".gdml")
    radius = surface_radius(layers)
    local_segments[:, :, 2] = np.linalg.norm(segments, axis=2) - radius

    codes, counts = np.unique(particle_codes, return_counts=True)
    order = np.argsort(counts)[::-1]
    codes = codes[order]
    display_codes = list(codes[:SHOWER_SPECIES_LIMIT])
    colors = plt.get_cmap("tab10")(np.linspace(0.0, 1.0, len(display_codes)))
    color_by_code = dict(zip(display_codes, colors))
    other_color = np.asarray([0.55, 0.55, 0.55, 0.45])
    segment_colors = np.asarray(
        [color_by_code.get(code, other_color) for code in particle_codes]
    )
    segment_colors[:, 3] = np.where(parent_ids == 0, 0.9, 0.5)

    radii = np.linalg.norm(local_segments[:, :, :2], axis=2)
    altitude_or_depth = local_segments[:, :, 2]
    plot_segments = np.stack((radii, altitude_or_depth), axis=2)

    radius_upper = np.max(radii)
    interactions = ~np.isin(
        step_processes,
        ("Transportation", "NoProcess", "none"),
    )
    if np.any(interactions):
        visible_vertical = altitude_or_depth[interactions]
    else:
        visible_vertical = altitude_or_depth
    vertical_lower = np.min(visible_vertical)
    vertical_upper = np.max(visible_vertical)
    vertical_padding = max(
        (vertical_upper - vertical_lower) * INTERACTION_ALTITUDE_MARGIN,
        MINIMUM_ALTITUDE_MARGIN_KM,
    )
    vertical_limits = (
        vertical_lower - vertical_padding,
        vertical_upper + vertical_padding,
    )

    figure, axis = plt.subplots(figsize=(9, 10), layout="constrained")
    collection = LineCollection(
        plot_segments,
        colors=segment_colors,
        linewidths=np.where(parent_ids == 0, 1.4, 0.65),
    )
    axis.add_collection(collection)
    axis.set_xlim(0.0, radius_upper * 1.04 if radius_upper else 1.0)
    axis.set_ylim(*vertical_limits)
    axis.set_xlabel("Transverse radius r [km]")
    setup_shell_axis(axis)
    axis.grid(alpha=0.25)

    legend_entries = [
        Line2D(
            [0],
            [0],
            color=color_by_code[code],
            linewidth=2,
            label=particle_symbol(int(code)),
        )
        for code in display_codes
    ]
    if len(codes) > len(display_codes):
        legend_entries.append(
            Line2D([0], [0], color=other_color, linewidth=2, label="other")
        )
    axis.legend(
        handles=legend_entries,
        title="Particle",
        loc="upper left",
        ncols=2,
    )
    axis.set_title(
        "%s shower event %i: %s steps in %s tracks"
        % (
            simname.capitalize(),
            event_id,
            format(step_count, ","),
            format(track_count, ","),
        )
    )
    filename = simname + ".shower.png"
    figure.savefig(filename, dpi=180)
    plt.close(figure)
    return filename


def plot_mode_one_output(simname):
    """Write aggregate and per-event plots for one mode-1 trace."""
    summary = read_step_trace(simname + ".root")
    return [
        plot_step_trace(simname, summary),
        plot_shower(simname, summary),
    ]
