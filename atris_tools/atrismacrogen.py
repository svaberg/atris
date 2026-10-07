"""
This is the new simplified simulator for Earth applications. 

Nessary input files: before you start a simulation, make sure to prepare the following input files:
  + the .psf file specifing the planetary model in a human readable format
  + the .gdml file that is created after running the psf file through the psf2gdml convertor.
  + the .spec file giving the differential spectrum of protons. The energy axis values of this file will be used as bins
  + the .spec file giving the differential spectrum of alphas. The energy axis values of this file will be used as bins

Phantoms:
  + The primary phantom is fixed: the ICRU sphere
  + Secondary phantom is choosen at start by entering one of the available names
  + The phantoms with "2" as sufix cannot consider the contribution to absorbed dose due to particles heavier than alpha particles.
  + the code is extremely sensitive on the proper definition of the phantom header. Take care not to change.
  + the new simulate.py automatically provides the correct mass and surface for the secondary phantom. 

Differential spectra:
  + The differential spectrum for protons should be provided as protons.spec.
  + The x-axis (first column)  is the energy per nucleon 
  + the y-axis (second column) is the differential spectrm j in 1 / (MeV m^2 s sr)
  + I is recommended to have 20 bins per decade. The binning is best created on a logarithmic scale. Exampel: 10**np.linspace(2,6,81) (here 81 is (6-2)*2+1)
  + The proton spectrum file protons.spec is mandatory
  + The alpha spectrum is also mandatory.
  + Twe two files need to have exactly the same bin edges! Note that the alpha spectrum needs to have its bins in "energy per nucleon". 
  + Thus a 100 MeV j corresponds to alphas of 400 MeV.
  + You need to calculate the spectra before you start the calculation!
  + pick a meaningful lower energy limit. If you have a certain magnetic cutoff rigidity, do not simulate too far below it.
  + The werkzeug tool can modify the cutoff rigidity for what-if investigations.
  + Use a meaningful upper energy limit. Typically, it is sufficent to go up to 100 GeV. 
  + I've prepared an example jupyter notebook illustrating the procedure. You can find it in the atris-werkzeug repository, under
    ./spectrum/spectrum_example.ipynb. To use it, cd in to the atris-workshop folder and start "jupyter lab" or "jupyter notebook".
    Note that I am using in this part python3. 
 
Other simulation settings:
  + These are best-practices which were investigated in my phd thesis:
    - with 1km shell thickness, you should expect approx 15% error at 5 km, for other altitudes, this error is lower.
    - 500m shells are better. 200m even better. 500m is 26% slower then 1000m, while 200m is  74% slower.
    - ion-electron production rate should be plotted at the bottom of the sheet. This reduces the error to 5% at 1000m shell thickness.
    - The same is true for dose rate values.
    - Optimal energy bin width was investigated in terms of "bins per decade".
    - 10 bins per decade gives you an error of 2%, while with 20 bins per decade you get 1%.
    - The total event count scales with the number of configured energy edges.

How to use:
    - The script works with python3
    - install geant4 as described in the presentation or on the wiki
    - Source "/install/path/install/bin/geant4.sh"
    - create the spec file for protons and name it protons.spec
    - create the spec file for alphas and name it alphas.spec
    - create the psf file and name it simulation.psf
    - Use the psf2gdml script to create a GDML file and name it simulation.gdml
    - build AtRIS within some directory
    - Copy simulate.py, simulate.psf, simulate.gdml, protons.spec, alphas.spec, simulation.desc, all the phantom files to the build directory
    - If you do not copy all of the necessary files, the simulation will not work.
    - Describe your simulation in the simulation.desc with a simple text editor
    - run python3 simulate.py
    - enter secondary phantom name (e.g. radb)
    - start simulation monitoring with "watch -n1 ./monitor"
    - after a dosen seconds you should see that the simulation is calculating particles
    - if you do not see two processor cores at 100%, something is wrong. Check the protons.out and protons.error file for more information.
"""
# Energy is constant
import argparse
import logging
import os
import random
import shutil

import numpy as np

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)
from .phantoms import configured_phantom_files, read_phantoms
from .psf import OUTER_RADIUS, load_psf


GENERATED_INPUTS = (
    "protons.mac",
    "protons.bins",
    "protons.gdml",
    "alphas.mac",
    "alphas.bins",
    "alphas.gdml",
)
DEFAULT_PHYSICS_LIST = "FTFP_BERT_HP"
DEFAULT_OUTPUT_MODE = "response"
DEFAULT_OUTPUT_FORMAT = "csv"
DIRECTION_HISTOGRAM_BINS = (120, 60)
POSITION_HISTOGRAM_BINS = (120, 60)
OUTPUT_MODES = ("response", "profile", "shower")
logger = logging.getLogger(__name__)


def _add_commands(lines, *commands):
    for comment, command in commands:
        lines.extend(("# " + comment, command))


def _add_section(lines, title, description, *commands):
    lines.extend(("", "# " + title, "# " + description))
    _add_commands(lines, *commands)


def refuse_existing_inputs(output_dir):
    existing = [
        filename
        for filename in GENERATED_INPUTS
        if os.path.lexists(os.path.join(output_dir, filename))
    ]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing AtRIS inputs: " + ", ".join(existing)
        )


def genMacro(
    nr1,
    nr2,
    N,
    name,
    particle,
    fact,
    thebins,
    radius,
    output_dir="./atris/simulation",
    physics_list=DEFAULT_PHYSICS_LIST,
    output_mode=DEFAULT_OUTPUT_MODE,
    output_format=DEFAULT_OUTPUT_FORMAT,
):
    lines = [
        "# AtRIS simulation macro for %s" % name,
        "# Generated by atris-generate-macros.",
        "#",
        "# Commands are applied from top to bottom.",
        "# /atris/ configures AtRIS inputs, scoring, and output.",
        "# /run/ initializes Geant4, controls transport, and starts events.",
        "# /gps/ configures Geant4's General Particle Source (GPS).",
    ]

    _add_section(
        lines,
        "AtRIS input and output files",
        "These AtRIS-specific settings must precede /run/initialize.",
        (
            "Read the detector geometry from this GDML file.",
            "/atris/geometryFile %s.gdml" % name,
        ),
        (
            "Read output energy-bin edges; GPS source sampling is configured below.",
            "/atris/energyBinsFile %s.bins" % name,
        ),
        (
            "Use this filename stem for all simulation output.",
            "/atris/outputStem %s" % name,
        ),
    )

    _add_section(
        lines,
        "Physics and output content",
        "Choose the Geant4 physics and the amount and format of saved data.",
        (
            "Use this Geant4 reference physics list for particle transport.",
            "/atris/physicsList %s" % physics_list,
        ),
        (
            {
                "response": "Save aggregate response histograms only.",
                "profile": "Also save every detector-interface crossing.",
                "shower": "Also save interface crossings and transport steps.",
            }[output_mode],
            "/atris/outputMode %s" % output_mode,
        ),
        (
            "Write analysis data using Geant4's %s backend." % output_format,
            "/atris/outputFormat %s" % output_format,
        ),
    )

    _add_section(
        lines,
        "Diagnostic histogram resolution",
        "These settings affect source diagnostic histograms, not sampling.",
    )
    for label, histogram, bins in (
        ("direction", "direction", DIRECTION_HISTOGRAM_BINS),
        ("position", "position", POSITION_HISTOGRAM_BINS),
    ):
        _add_commands(
            lines,
            (
                "Divide source-%s azimuth into %i histogram bins."
                % (label, bins[0]),
                "/atris/%sHistogram/azimuthBins %i" % (histogram, bins[0]),
            ),
            (
                "Divide source-%s cos(polar angle) into %i histogram bins."
                % (label, bins[1]),
                "/atris/%sHistogram/cosineBins %i" % (histogram, bins[1]),
            ),
        )

    _add_section(
        lines,
        "Phantom response scoring",
        "Each phantom block selects a name and registers one or more responses.",
    )
    lines.extend(
        (
            "# Each response starts with its table coefficient. The three scaleBy",
            "# settings independently apply crossing energy, radiation weight, and",
            "# inverse phantom mass. The first two act during transport; inverse",
            "# phantom mass is applied by atris-postprocess.",
            "# name labels the output, tableFile supplies coefficients, and add",
            "# registers the response and clears the response properties.",
        )
    )
    phantoms = read_phantoms(output_dir)
    if not phantoms:
        lines.append("# No phantom responses are configured for this run.")
    factor_commands = (
        "scaleByCrossingEnergy",
        "scaleByRadiationWeight",
        "scaleByInversePhantomMass",
    )
    for phantom in phantoms:
        response, counting = configured_phantom_files(output_dir, phantom)
        stem = os.path.basename(phantom["stem"])
        lines.extend(
            ("", "# Phantom: " + stem, "/atris/phantom/name %s" % stem)
        )
        for response_name, response_description, filename, factors in (
            ("dos", "absorbed dose", response.name, (True, False, True)),
            (
                "equi",
                "equivalent dose",
                response.name,
                (True, True, True),
            ),
            (
                "rates",
                "counting response",
                counting.name,
                (False, False, False),
            ),
        ):
            lines.extend(
                (
                    "",
                    "# Response: %s (name: %s)"
                    % (response_description, response_name),
                    "/atris/phantom/response/name %s" % response_name,
                    "/atris/phantom/response/tableFile %s" % filename,
                )
            )
            lines.extend(
                "/atris/phantom/response/%s %s"
                % (command, str(enabled).lower())
                for command, enabled in zip(factor_commands, factors)
            )
            lines.append("/atris/phantom/response/add")

    _add_section(
        lines,
        "Reproducibility",
        "Geant4 requires two positive seeds for this random-number stream.",
        (
            "Set the two random seeds before initialization.",
            "/atris/randomSeeds %i %i" % (nr1, nr2),
        ),
    )

    _add_section(
        lines,
        "Geant4 initialization and transport controls",
        "Initialization builds the configured geometry and physics processes.",
        (
            "Initialize Geant4 after all /atris/ configuration is complete.",
            "/run/initialize",
        ),
        (
            "Print Geant4 run-manager progress at verbosity level 2.",
            "/run/verbose 2",
        ),
        (
            "Set the global secondary-production range cut; this is not an energy.",
            "/run/setCut 100. m",
        ),
        (
            "Print the resulting material-dependent production cuts.",
            "/run/particle/dumpCutValues",
        ),
    )

    bins = thebins * fact
    np.savetxt(os.path.join(output_dir, name + '.bins'), bins)
    _add_section(
        lines,
        "GPS primary particle and energy",
        "The General Particle Source creates the primary particle for each event.",
        ("Generate this particle species.", "/gps/particle %s" % particle),
        (
            "Sample kinetic energy from a power-law distribution.",
            "/gps/ene/type Pow",
        ),
        (
            "Set the minimum primary kinetic energy.",
            "/gps/ene/min %.9f MeV" % bins[0],
        ),
        (
            "Set the maximum primary kinetic energy.",
            "/gps/ene/max %.9f MeV" % bins[-1],
        ),
        (
            "Use an E^-1 power law, which is uniform in log kinetic energy.",
            "/gps/ene/alpha -1",
        ),
    )

    _add_section(
        lines,
        "GPS primary position and direction",
        "Primaries start on a sphere and travel inward through the model.",
        (
            "Sample positions on a surface rather than inside a volume.",
            "/gps/pos/type Surface",
        ),
        ("Use a spherical source surface.", "/gps/pos/shape Sphere"),
        ("Center the source sphere on the planet model.", "/gps/pos/centre 0 0 0 m"),
        (
            "Place the source 1 m beyond the atmosphere (the penultimate PSF layer).",
            "/gps/pos/radius %.3f km" % radius,
        ),
        (
            "Use cosine-law incidence about the inward surface normal.",
            "/gps/ang/type cos",
        ),
        (
            "Set the minimum polar angle from the inward normal.",
            "/gps/ang/mintheta 0 deg",
        ),
        ("Limit directions to the inward hemisphere.", "/gps/ang/maxtheta 90 deg"),
        (
            "Generate one primary particle per Geant4 event.",
            "/gps/number 1",
        ),
    )

    _add_section(
        lines,
        "Run events",
        "This final command starts particle transport.",
        (
            "Process %i events with the configuration above." % N,
            "/run/beamOn %i" % N,
        ),
    )
    lines.extend(("", "# End of AtRIS simulation macro."))
    return "\n".join(lines) + "\n"


def macroSetup(
    prefix,
    particle,
    fact,
    partspb,
    output_dir="./atris/simulation",
    base_bins=None,
    rng=None,
    physics_list=DEFAULT_PHYSICS_LIST,
    output_mode=DEFAULT_OUTPUT_MODE,
    output_format=DEFAULT_OUTPUT_FORMAT,
):
    if base_bins is None:
        base_bins = 10**np.linspace(0,6,121)
    if rng is None:
        rng = random
    radius  = load_psf(os.path.join(output_dir, 'simulation.psf'))[-2, OUTER_RADIUS] + 0.001 # we add 1 meter to the radius to aviod overlap.
    # We are taking two random seeds. Control this for the ability to reproduce.
    seed1     = rng.randint(31,999999)
    seed2     = rng.randint(31,999999)
    shutil.copy2(
        os.path.join(output_dir, 'simulation.gdml'),
        os.path.join(output_dir, prefix + '.gdml'),
    )
    lines = genMacro(
        seed1,
        seed2,
        base_bins.shape[0] * partspb,
        prefix,
        particle,
        fact,
        base_bins,
        radius,
        output_dir,
        physics_list,
        output_mode,
        output_format,
    )
    with open(os.path.join(output_dir, prefix + '.mac'), 'w') as filehandle:
        filehandle.write(lines)
    

def macroGenManager(
    partspb,
    alphafactor=1.0,
    output_dir="./atris/simulation",
    random_seed=None,
    energy_min_power=0.0,
    energy_max_power=6.0,
    energy_points=121,
    physics_list=DEFAULT_PHYSICS_LIST,
    output_mode=DEFAULT_OUTPUT_MODE,
    output_format=DEFAULT_OUTPUT_FORMAT,
):
    if energy_points < 2:
        raise ValueError("energy_points must be at least 2")
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        raise FileNotFoundError("Run directory does not exist: " + output_dir)
    refuse_existing_inputs(output_dir)
    rng = random.Random(random_seed) if random_seed is not None else random
    base_bins = 10**np.linspace(energy_min_power,energy_max_power,energy_points)
    macroSetup(
        'protons', "proton", 1, partspb, output_dir,
        base_bins, rng, physics_list, output_mode, output_format,
    )
    macroSetup(
        'alphas', "alpha", 4, int(partspb*alphafactor),
        output_dir, base_bins, rng, physics_list, output_mode, output_format,
    )


def main():
    """Run the AtRIS macro-generation command."""
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Generate the proton and alpha macros, energy grids, and geometry "
            "copies needed to run AtRIS."
        ),
        epilog=(
            "RUN_DIRECTORY must already contain simulation.psf and "
            "simulation.gdml. This command does not run AtRIS or stage phantom "
            "responses. It writes protons/alphas .mac, .bins, and .gdml files "
            "and refuses to overwrite any of them. The proton event count is "
            "PARTICLES_PER_BIN multiplied by ENERGY_POINTS; the alpha count "
            "uses the truncated PARTICLES_PER_BIN times ALPHA_FACTOR as its "
            "factor. Alpha energies are four times the corresponding proton "
            "grid values."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        default=".",
        metavar="RUN_DIRECTORY",
        help="Prepared run directory (default: current directory).",
    )
    parser.add_argument(
        "--particles-per-bin",
        type=int,
        default=3000,
        metavar="COUNT",
        help=(
            "Proton event-count factor multiplied by ENERGY_POINTS "
            "(default: 3000)."
        ),
    )
    parser.add_argument(
        "--alpha-factor",
        type=float,
        default=0.66,
        metavar="FACTOR",
        help=(
            "Alpha event-count factor as a fraction of the proton factor; "
            "the result is truncated to an integer (default: 0.66)."
        ),
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        metavar="SEED",
        help="Seed for reproducible Geant4 seed pairs (default: random).",
    )
    parser.add_argument(
        "--energy-min-power",
        type=float,
        default=0.0,
        metavar="POWER",
        help=(
            "Base-10 exponent of the minimum proton energy in MeV "
            "(default: 0, or 1 MeV)."
        ),
    )
    parser.add_argument(
        "--energy-max-power",
        type=float,
        default=6.0,
        metavar="POWER",
        help=(
            "Base-10 exponent of the maximum proton energy in MeV "
            "(default: 6, or 1 TeV)."
        ),
    )
    parser.add_argument(
        "--energy-points",
        type=int,
        default=121,
        metavar="COUNT",
        help=(
            "Number of logarithmically spaced output-bin edges, including "
            "both endpoints (default: 121)."
        ),
    )
    parser.add_argument(
        "--physics-list",
        default=DEFAULT_PHYSICS_LIST,
        metavar="NAME",
        help=(
            "Geant4 reference physics list recorded in both macros "
            "(default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--output-mode",
        choices=OUTPUT_MODES,
        default=DEFAULT_OUTPUT_MODE,
        help="AtRIS output mode recorded in both macros (default: %(default)s).",
    )
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        metavar="FORMAT",
        help=(
            "Geant4 analysis output format recorded in both macros "
            "(default: %(default)s)."
        ),
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)
    logger.debug(
        "Generating inputs with event-count factor %i, %i output-bin edges, "
        "and alpha factor %.3g",
        args.particles_per_bin,
        args.energy_points,
        args.alpha_factor,
    )
    macroGenManager(
        args.particles_per_bin,
        args.alpha_factor,
        args.run_directory,
        args.random_seed,
        args.energy_min_power,
        args.energy_max_power,
        args.energy_points,
        args.physics_list,
        args.output_mode,
        args.output_format,
    )
    logger.info(
        "Generated proton and alpha input files in %s",
        os.path.abspath(args.run_directory),
    )


if __name__ == "__main__":
    main()
