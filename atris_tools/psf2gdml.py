import argparse
import os
import re
from pathlib import Path

import numpy as np

from .cli import HelpFormatter, add_version_argument
from .psf import (
    INNER_RADIUS,
    OUTER_RADIUS,
    PHI_START,
    PHI_END,
    THETA_START,
    THETA_END,
    DETECTOR_ID,
    TEMPERATURE,
    DENSITY,
    PRESSURE,
    STATE,
    FIRST_ELEMENT,
    load_psf,
    read_psf_header,
)

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# We load "nist.exist", which holds information about which materials already
# exist in the Geant4 material database. This information is useful when
# creating sheet materials.
f = open(os.path.join(data_dir, "nist.exist"), "r")
nistdb = f.readline()
# Appending own materials. Here, I should add all the project-related molecules
nistdb = nistdb[:-1] + ",'G4_VACUUM']"
f.close()


def parse_solid(formula):
    """
    parse_solid is ment to deal with the first element in the header.
    In the PSF format spec, we have described in detail the representation
    of the header. To summarize, the first element is a series of chemical
    elements followed by their mass fraction in per milles. For example,
    O762C111H101N26 corresponds to:
        : 762 parts oxygen
        : 111 parts carbon
        : 101 parts hydrogen
        :  26 parts nitrogen
        ====================
        :1000 parts
    Notes:
        - Sum of per milles should add up to 1000
        - Order according to decreasing abundance
        - This is only for the header! The GDML material will be designated
          as a "solid"
        - The macroscopic properties of the core elemnts still have to be
          provided in the first line of the PSF file.
    """
    # convert formula using regular expressions in to a list of tuples
    first = re.findall(r"([A-Z][a-z]*)(\d*)", formula)
    for k in first:
        element = k[0]
    if element not in nistdb:
        print("element not found in the nist database. ABORTING!!")
        return 0
    g4mat, totalmass = {}, 0.0
    for k in first:
        material = k[0]
        massfrac = float(k[1]) / 1000.0
        g4mat.update({material: {"mass fraction": massfrac, "material": material}})
        totalmass += massfrac
    if np.abs(totalmass - 1.0) > 0.0001:
        print(
            "\ttotal mass is not equal to 1!!\n\t\t\tformula: %s\n\t\t\ttotalmas: %.10f. Rescaling."
            % (formula, totalmass)
        )
        new_g4mat = {}
        new_totalmass = 0.0
        factor = 1.0 / totalmass
        for k in first:
            material = k[0]
            massfrac = float(k[1]) / 1000.0 * factor
            new_g4mat.update(
                {material: {"mass fraction": massfrac, "material": material}}
            )
            new_totalmass += massfrac
        if np.abs(new_totalmass - 1.0) > 0.0001:
            print(
                "\ttotal mass is AGAIN not equal to 1!! formula: %s totalmas: %.10f. Serious problem encuntered."
                % (formula, new_totalmass)
            )
        else:
            print("\ttotal mass is now fine. Problem solved.")
        return new_g4mat
    return g4mat


def gdml_material(mat, name, temperature, density, pressure, state="solid"):
    """
    # units for T, rho, P are K, g/ccm, Pa
    This function is specially tailored for the solid materials, which are
    to be used for the core and the crust, but it can be also used to make
    gaseous materials.
    """
    header = '\t<material name="%s" state="%s">\n' % (name, state)
    footer = "\t</material>\n"
    output = ""
    output += header
    output += '\t\t<D value="%e" unit="g/cm3" />\n' % density
    output += '\t\t<T value="%e" unit="K" />\n' % temperature
    output += '\t\t<P value="%e" unit="Pa" />\n' % pressure
    for key in mat:
        frac, name = mat[key]["mass fraction"], mat[key]["material"]
        if frac != 0.0:
            current = '\t\t<fraction n="%e" ref="G4_%s" />\n' % (frac, name)
            output += current
    output += footer
    return output


def parse_header(filename):
    header = read_psf_header(filename)
    nrformulas = len(header)

    # Generate the header gdml text
    coremat = parse_solid(header[0])

    # generate template dictionary for other sheets
    template = {}
    idx = 0
    for material in header[1:]:
        template.update(
            {material: {"mass fraction": 0, "material": material, "colidx": idx}}
        )
        idx += 1
    return coremat, template


def line_processor(filename):
    core, template = parse_header(filename)
    # now we generate the gdml material blocks
    data = load_psf(filename)
    nrsheets = data.shape[0]
    expected_columns = FIRST_ELEMENT + len(template)
    assert data.shape[1] == expected_columns, "PSF has %i columns; expected %i" % (
        data.shape[1],
        expected_columns,
    )

    # We generate the materials and geometry entries
    materials, geometry, struct = [], [], []
    for aLine in data:
        state_code = aLine[STATE]
        state = {1.0: "solid", 2.0: "liquid"}.get(state_code, "gas")
        sdid = int(aLine[DETECTOR_ID])
        name = "material" + str(sdid)
        temp = aLine[TEMPERATURE]
        dens = aLine[DENSITY]
        pres = aLine[PRESSURE]
        rowmat = {}
        for mat in template:
            nname = template[mat]["material"]
            idx = FIRST_ELEMENT + template[mat]["colidx"]
            rowmat[nname] = {
                "mass fraction": aLine[idx],
                "material": nname,
            }
        material = (
            core
            if state_code == 1.0
            and all(item["mass fraction"] == 0.0 for item in rowmat.values())
            else rowmat
        )
        materials.append(gdml_material(material, name, temp, dens, pres, state))
        # now the geometry  entry
        solname = "solid" + str(int(aLine[DETECTOR_ID]))
        rmin = aLine[INNER_RADIUS]
        rmax = aLine[OUTER_RADIUS]
        phimin = aLine[PHI_START]
        phimax = aLine[PHI_END]
        phimax = phimax - phimin
        if np.abs(phimax - 2.0 * np.pi) < 0.01:
            phimax = "TWOPI"
        thetamin = aLine[THETA_START]
        thetamax = aLine[THETA_END]
        thetamax = thetamax - thetamin
        if np.abs(thetamax - np.pi) < 0.01:
            thetamax = "PI"
        if thetamax == 2.0:
            thetamax = "PI"
        sphere = (
            '\t<sphere name="%s" rmin="%f" rmax="%f" startphi="%.4f" deltaphi="%s" starttheta="%.4f" deltatheta="%s" lunit="km" aunit="rad"/>\n'
            % (solname, rmin, rmax, phimin, str(phimax), thetamin, str(thetamax))
        )
        geometry.append(sphere)
        struct.append(["volume" + str(sdid), name, solname, sdid])
    wrld = data[-1, OUTER_RADIUS]
    return materials, geometry, struct, wrld


def gdml_compile(materials, world, geometry, structure, filename):
    finalfile = ""
    header = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<gdml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://service-spi.web.cern.ch/service-spi/app/releases/GDML/schema/gdml.xsd">\n\n\n\n'
    footer = '\n<setup name="Exoplanet" version="1.0">\n\t<world ref="World"/>\n</setup>\n</gdml>'
    finalfile += header

    # now the <define> part
    # here we need to modify the offset of the world box.
    define = '<define>\n\t<constant name="PI" value="1.*pi"/>\n\t<constant name="TWOPI" value="2.*pi"/>\n\t<position name="center"/>\n\t<rotation name="identity"/>\n</define>\n'
    finalfile += define

    # Now the materials
    finalfile += "<materials>\n"
    # We also add the AtRIS material extensions
    f = open(os.path.join(data_dir, "atris.materials"), "r")
    ff = f.readlines()
    for fff in ff:
        finalfile += fff
    f.close()
    for mat in materials:
        finalfile += mat
    finalfile += "</materials>\n"
    # Now the geometry
    finalfile += "<solids>\n"
    # add the world
    wd = world * 2
    add = '\t<box name="WorldBox" x="%f" y="%f" z="%f" lunit="km"/>\n' % (wd, wd, wd)
    finalfile += add

    for vol in geometry:
        finalfile += vol
    finalfile += "</solids>\n"

    # now the structure
    finalfile += "<structure>\n"
    for st in structure:
        add = (
            '\t<volume name="%s">\n\t\t<materialref ref="%s"/>\n\t\t<solidref ref="%s"/>\n\t\t<auxiliary auxtype="SensDet" auxvalue="%i"/>\n\t</volume>\n'
            % tuple(st)
        )
        finalfile += add
    # now we need to add the world and place all the other volumes
    worldpart = '\t<volume name="World">\n\t\t<materialref ref="Vacuum"/>\n\t\t<solidref ref="WorldBox"/>\n'
    finalfile += worldpart
    for st in structure:
        vv = st[0]
        add = (
            '\t\t<physvol>\n\t\t\t<volumeref ref="%s"/>\n\t\t\t<positionref ref="center"/>\n\t\t</physvol>\n'
            % vv
        )
        finalfile += add
    finalfile += "\t</volume>\n"
    finalfile += "</structure>\n"
    # Now the footer
    finalfile += footer
    f = open(filename, "w")
    f.write(finalfile)
    f.close()


def psf2gdml(input_path, output_path=None):
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path.with_suffix(".gdml")
    materials, geometry, structure, world = line_processor(input_path)
    gdml_compile(
        materials,
        world + 100,
        geometry,
        structure,
        output_path,
    )
    return output_path


def main():
    """Convert an AtRIS PSF file to GDML."""
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Convert an AtRIS Planet Specification Format model into the GDML "
            "geometry and material description read by Geant4."
        ),
        epilog=(
            "The output defaults to the input basename with a .gdml suffix. "
            "An existing output file is replaced. This command does not "
            "download or generate an atmosphere and does not run AtRIS."
        ),
    )
    parser.add_argument(
        "psf_file",
        type=Path,
        metavar="PSF_FILE",
        help="PSF model to convert.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="GDML_FILE",
        help="GDML file to write (default: input basename with .gdml suffix).",
    )
    add_version_argument(parser)
    args = parser.parse_args()
    psf2gdml(args.psf_file, args.output)


if __name__ == "__main__":
    main()
