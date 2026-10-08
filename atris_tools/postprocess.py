#!/usr/bin/env python3
"""Convert raw AtRIS histograms into scaled numerical response files."""

import argparse
import logging
import os
from pathlib import Path

import numpy as np

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)
from .phantoms import read_phantoms
from .psf import (
    INNER_RADIUS,
    OUTER_RADIUS,
    PHI_START,
    PHI_END,
    THETA_START,
    THETA_END,
    DETECTOR_ID,
    load_psf,
)
from .response_histograms import (
    IONIZATION_HISTOGRAM,
    PRIMARY_HISTOGRAM,
    TOTAL_DEPOSITION_HISTOGRAM,
    ResponseHistogramReader,
    csv_histogram_path,
    response_output_format,
)
from .units import energy_to_mev

logger = logging.getLogger(__name__)


def process_psf(filename="simulation.psf"):
    data = load_psf(filename)
    rmin = data[:, INNER_RADIUS] * 100000.0
    rmax = data[:, OUTER_RADIUS] * 100000.0
    delta_phi = data[:, PHI_END] - data[:, PHI_START]
    theta_factor = np.cos(data[:, THETA_START]) - np.cos(data[:, THETA_END])
    inner_surface = delta_phi * rmin**2 * theta_factor
    outer_surface = delta_phi * rmax**2 * theta_factor
    volume = delta_phi * theta_factor * (rmax**3 - rmin**3) / 3.0

    core = inner_surface == 0
    inner_surface[core] = outer_surface[core]

    order = np.argsort(inner_surface, kind="stable")
    geometry = {
        "sdid": data[:, DETECTOR_ID].astype(int)[order],
        "volume/cm3": volume[order],
        "inn_surface/cm2": inner_surface[order],
    }
    return geometry, data.shape[0]


def _read_macro_configuration(filename):
    energy_limits = {}
    event_count = None
    with open(filename) as macro:
        for line in macro:
            fields = line.split()
            if not fields or fields[0].startswith("#"):
                continue
            if fields[0] in ("/gps/ene/min", "/gps/ene/max"):
                unit = fields[2] if len(fields) > 2 else "keV"
                energy_limits[fields[0]] = energy_to_mev(fields[1], unit)
            elif fields[0] == "/run/beamOn":
                event_count = int(fields[1])
    if len(energy_limits) == 2:
        energy_range = np.asarray(
            [energy_limits["/gps/ene/min"], energy_limits["/gps/ene/max"]]
        )
    else:
        energy_range = np.asarray([])
    return energy_range, event_count


def _input_output_warnings(simname, histograms):
    warnings = []

    def output_name(name):
        if histograms.format == "root":
            return simname + ".root"
        return csv_histogram_path(simname, name).name

    bins_path = Path(simname + ".bins")
    macro_path = Path(simname + ".mac")

    output_edges = histograms.axes(PRIMARY_HISTOGRAM)[0]
    input_edges = None
    if bins_path.is_file():
        input_edges = np.atleast_1d(np.loadtxt(bins_path))
        if input_edges.shape != output_edges.shape or not np.allclose(
            input_edges, output_edges
        ):
            warnings.append(
                "%s: %s does not match the energy edges recorded in %s"
                % (simname, bins_path.name, output_name(PRIMARY_HISTOGRAM))
            )

    if macro_path.is_file():
        macro_range, event_count = _read_macro_configuration(macro_path)
        if input_edges is not None and (
            macro_range.shape != (2,)
            or not np.allclose(macro_range, input_edges[[0, -1]])
        ):
            warnings.append(
                "%s: %s energy range does not match %s"
                % (simname, macro_path.name, bins_path.name)
            )
        if event_count is not None and not Path("chunks.txt").is_file():
            primary_energy = histograms.values(PRIMARY_HISTOGRAM)
            recorded_events = int(np.sum(primary_energy[1:-1]))
            if recorded_events != event_count:
                warnings.append(
                    "%s: %s requests %i events, but %s records %i"
                    % (
                        simname,
                        macro_path.name,
                        event_count,
                        output_name(PRIMARY_HISTOGRAM),
                        recorded_events,
                    )
                )

    psf_path = Path("simulation.psf")
    if psf_path.is_file() and IONIZATION_HISTOGRAM in histograms.names():
        detector_count = load_psf(psf_path).shape[0]
        output_detector_count = len(histograms.axes(IONIZATION_HISTOGRAM)[1]) - 1
        if output_detector_count != detector_count:
            warnings.append(
                "%s: %s defines %i detector layers, but %s records %i"
                % (
                    simname,
                    psf_path.name,
                    detector_count,
                    output_name(IONIZATION_HISTOGRAM),
                    output_detector_count,
                )
            )

    histogram_names = histograms.names()
    for name, description in (
        ("h2.dir", "source-direction"),
        ("h2.pos", "source-position"),
    ):
        if name not in histogram_names:
            continue
        values = histograms.values(name)
        flow_entries = values.sum() - values[1:-1, 1:-1].sum()
        if not np.isclose(flow_entries, 0.0):
            warnings.append(
                "%s: %s contains %g entries in the %s histogram's "
                "underflow or overflow bins"
                % (simname, output_name(name), flow_entries, description)
            )

    phantom_path = Path("phantoms.txt")
    if phantom_path.is_file():
        configured_stems = {
            Path(phantom["stem"]).name for phantom in read_phantoms(Path.cwd())
        }
        output_stems = histograms.phantom_stems()
        if output_stems != configured_stems:
            warnings.append(
                "%s: %s selects %s, but raw output contains %s"
                % (
                    simname,
                    phantom_path.name,
                    ", ".join(sorted(configured_stems)) or "no phantoms",
                    ", ".join(sorted(output_stems)) or "no phantoms",
                )
            )
    return warnings


def input_output_warnings(simname):
    with ResponseHistogramReader(simname) as histograms:
        return _input_output_warnings(simname, histograms)


def warn_if_inputs_do_not_match_output(simname):
    for warning in input_output_warnings(simname):
        logger.warning("%s", warning)


def process_phantoms(phantom_stems):
    if not phantom_stems:
        return np.empty((0, 2))
    phantoms = {
        Path(phantom["stem"]).name: phantom for phantom in read_phantoms(Path.cwd())
    }
    missing = set(phantom_stems) - phantoms.keys()
    if missing:
        raise ValueError(
            "phantoms.txt has no metadata for " + ", ".join(sorted(missing))
        )
    return np.array(
        [[phantoms[stem]["mass"], phantoms[stem]["area"]] for stem in phantom_stems]
    )


def scale_data(
    data,
    responses,
    phantom_stems,
    phantom_data,
    geometry,
    atmospheric_response_count=1,
):
    nrparticles = data[0][1:-1]
    phantom_start = 3 + atmospheric_response_count
    for hist_index in range(3, phantom_start):
        new_data = data[hist_index][1:-1, 1:-1].T
        data[hist_index] = new_data / nrparticles[None, :]
        data[hist_index] = data[hist_index] / geometry["volume/cm3"][:, None]
    phantom_indices = {stem: index for index, stem in enumerate(phantom_stems)}
    for response_index, response in enumerate(responses):
        hist_index = phantom_start + response_index
        new_data = data[hist_index][1:-1, 1:-1].T
        data[hist_index] = new_data / nrparticles[None, :]
        phantom_nr = phantom_indices[response.phantom_stem]
        phantom_surface = phantom_data[phantom_nr, 1]
        if response.scale_by_inverse_phantom_mass:
            phantom_surface = phantom_surface / phantom_data[phantom_nr, 0]
        data[hist_index] = (
            data[hist_index] * phantom_surface / geometry["inn_surface/cm2"][:, None]
        )
    return data


def make_output(
    data,
    geometry,
    simname,
    responses,
    atmospheric_extensions=(".ioni",),
):
    altitude = (geometry["inn_surface/cm2"] / (4.0 * np.pi)) ** 0.5 / 100000.0
    altitude = altitude - altitude[2]
    altitude = altitude[1:-1, None]
    sdid = geometry["sdid"][1:-1, None]
    number_format = ["%.5e"] * data[3].shape[1]
    number_format = ["%8.3f"] + number_format
    number_format = ["%5i"] + number_format
    phantom_start = 3 + len(atmospheric_extensions)
    outputs = [
        (3 + offset, extension)
        for offset, extension in enumerate(atmospheric_extensions)
    ]
    response_extensions = {"dos": "dose"}
    outputs.extend(
        (
            phantom_start + response_index,
            ".%s.%s"
            % (
                response.phantom_stem,
                response_extensions.get(response.name, response.name),
            ),
        )
        for response_index, response in enumerate(responses)
    )
    for hist_index, extension in outputs:
        histogram_data = data[hist_index][1:-1, :]
        output_data = np.hstack((sdid, altitude, histogram_data))
        np.savetxt(
            simname + extension,
            output_data,
            fmt=number_format,
            delimiter=" ",
            encoding="utf-8",
        )


def process_run(simname):
    with ResponseHistogramReader(simname) as histograms:
        for warning in _input_output_warnings(simname, histograms):
            logger.warning("%s", warning)
        geometry, _ = process_psf()
        responses = histograms.response_definitions()
        phantom_stems = sorted({response.phantom_stem for response in responses})
        phantom_count = len(phantom_stems)
        energy_edges = histograms.axes(PRIMARY_HISTOGRAM)[0]
        phantom_data = process_phantoms(phantom_stems)
        logger.info(
            "Post-processing %s %s output with %i energy bins and %i phantoms",
            simname,
            histograms.format.upper(),
            energy_edges.shape[0] - 1,
            phantom_count,
        )
        logger.debug("Reading %s histogram data", simname)
        atmospheric_outputs = [(IONIZATION_HISTOGRAM, ".ioni")]
        if TOTAL_DEPOSITION_HISTOGRAM in histograms.names():
            atmospheric_outputs.append((TOTAL_DEPOSITION_HISTOGRAM, ".edep"))
        names = [PRIMARY_HISTOGRAM, "h2.dir", "h2.pos"]
        names += [name for name, _ in atmospheric_outputs]
        names += [response.histogram_name for response in responses]
        data = [histograms.values(name) for name in names]
    logger.debug("Scaling %s response data", simname)
    scaled_data = scale_data(
        data,
        responses,
        phantom_stems,
        phantom_data,
        geometry,
        atmospheric_response_count=len(atmospheric_outputs),
    )
    logger.debug("Writing %s response files", simname)
    make_output(
        scaled_data,
        geometry,
        simname,
        responses,
        atmospheric_extensions=tuple(extension for _, extension in atmospheric_outputs),
    )
    logger.info("Wrote processed %s response files", simname)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Scale canonical AtRIS CSV or ROOT histograms into altitude- and "
            "energy-dependent atmospheric energy-deposition and phantom "
            "response tables."
        ),
        epilog=(
            "The command processes the selected simulation prefixes when their "
            "primary histogram files are present. It reads simulation.psf and, "
            "for phantom responses, phantoms.txt; it writes .ioni, .edep when "
            "total-deposition input is present, and one stem- and response-named "
            "file per phantom response, replacing existing processed files. "
            "Missing species are skipped. This command does not gather chunk "
            "histograms, run simulations, or make plots."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        metavar="RUN_DIRECTORY",
        help="Run directory containing canonical response output (default: current directory).",
    )
    parser.add_argument(
        "simulations",
        nargs="*",
        default=("protons", "alphas"),
        metavar="SIMULATION",
        help="Simulation prefixes to process (default: protons alphas).",
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)

    run_directory = args.run_directory.expanduser().resolve()
    if not run_directory.is_dir():
        raise SystemExit("Run directory does not exist: " + str(run_directory))

    previous_directory = Path.cwd()
    processed = []
    logger.info("Starting post-processing in %s", run_directory)
    try:
        os.chdir(run_directory)
        for simulation in args.simulations:
            if response_output_format(simulation) is None:
                logger.info("Skipping %s: output not found", simulation)
                continue
            process_run(simulation)
            processed.append(simulation)
    finally:
        os.chdir(previous_directory)

    if processed:
        logger.info("Wrote processed result files to %s", run_directory)
    else:
        logger.info("No requested simulation output found in %s", run_directory)


if __name__ == "__main__":
    main()
