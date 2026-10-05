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
    - Since we are fixing the number of particles per bin, 20 bins is 2x more expensive computationaly then 10 bins per decade.
    - Per bin you should have 5000 particles. 

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
logger = logging.getLogger(__name__)


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
    part,
    fact,
    thebins,
    radius,
    output_dir="./atris/simulation",
    physics_list=DEFAULT_PHYSICS_LIST,
):
    lines =  ""
    lines += "/atris/physicsList %s\n" % physics_list
    lines += "/run/initialize\n"
    lines += "/run/verbose 2\n"
    lines += part
    lines += "/gps/ene/type User\n"
    lines += "/gps/hist/type energy\n"
    bins   = thebins*fact
    np.savetxt(os.path.join(output_dir, name + '.bins'), bins)
    lines += "/gps/hist/point %.9f %.9f\n"%(bins[0],0.0)
    for thebin in bins[1:]:
        lines += "/gps/hist/point %.9f %.9f\n"%(thebin,1.0)
    lines += "/gps/pos/type Surface\n"
    lines += "/gps/pos/shape Sphere\n"
    lines += "/gps/pos/centre 0 0 0 m\n"
    lines += "/gps/pos/radius %.3f km\n"%radius #THIS HAS TO BE CONFIGURED MANUALLY!
    lines += "/gps/ang/type cos\n"
    lines += "/gps/ang/mintheta 0 deg\n"
    lines += "/gps/ang/maxtheta 90 deg\n"
    lines += "/gps/number 1\n"
    lines += "/run/setCut 100. m\n"           #CONFIGURE
    lines += "/run/particle/dumpCutValues\n"
    lines += "/random/setSeeds %i %i\n"%(nr1,nr2)
    lines += "/run/beamOn %i\n"%N
    return lines


def macroSetup(
    prefix,
    part,
    fact,
    partspb,
    output_dir="./atris/simulation",
    base_bins=None,
    rng=None,
    physics_list=DEFAULT_PHYSICS_LIST,
):
    if base_bins is None:
        base_bins = 10**np.linspace(0,6,121)
    if rng is None:
        rng = random
    radius  = load_psf(os.path.join(output_dir, 'simulation.psf'))[-2, OUTER_RADIUS] + 0.001 # we add 1 meter to the radius to aviod overlap.
    bins    = base_bins
    N       = bins.shape[0]*partspb # At 20 bins per decade, 2500 particles per bin is good. Even better would be 5k or 10k.
    # We are taking two random seeds. Control this for the ability to reproduce.
    seed1     = rng.randint(31,999999)
    seed2     = rng.randint(31,999999)
    #name      = str(seed1)+prefix
    name      = prefix
    shutil.copy2(os.path.join(output_dir, 'simulation.gdml'), os.path.join(output_dir, name + '.gdml'))
    lines = genMacro(seed1,seed2,N,name,part,fact,bins,radius,output_dir,physics_list)
    filehandle = open(os.path.join(output_dir, name + '.mac'), 'w')
    filehandle.writelines(lines)
    filehandle.close()
    

def macroGenManager(
    partspb,
    alphafactor=1.0,
    output_dir="./atris/simulation",
    random_seed=None,
    energy_min_power=0.0,
    energy_max_power=6.0,
    energy_points=121,
    physics_list=DEFAULT_PHYSICS_LIST,
):
    if energy_points < 2:
        raise ValueError("energy_points must be at least 2")
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        raise FileNotFoundError("Run directory does not exist: " + output_dir)
    refuse_existing_inputs(output_dir)
    rng = random.Random(random_seed) if random_seed is not None else random
    base_bins = 10**np.linspace(energy_min_power,energy_max_power,energy_points)
    macroSetup('protons',"/gps/particle proton\n",1,partspb,output_dir,base_bins,rng,physics_list)
    macroSetup('alphas',"/gps/particle alpha\n",4,int(partspb*alphafactor),output_dir,base_bins,rng,physics_list)


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
            "uses ALPHA_FACTOR per energy point. Alpha energies are four times "
            "the corresponding proton grid values."
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
        help="Number of proton histories per energy point (default: 3000).",
    )
    parser.add_argument(
        "--alpha-factor",
        type=float,
        default=0.66,
        metavar="FACTOR",
        help=(
            "Alpha histories per energy point as a fraction of the proton "
            "count; the result is truncated to an integer (default: 0.66)."
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
            "Number of logarithmically spaced energy points, including both "
            "endpoints (default: 121)."
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
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)
    logger.debug(
        "Generating inputs with %i particles per bin, %i energy points, "
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
    )
    logger.info(
        "Generated proton and alpha input files in %s",
        os.path.abspath(args.run_directory),
    )


if __name__ == "__main__":
    main()
