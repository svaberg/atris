import os
import sys

import numpy as np

from atris_tools.psf import (
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
)

# I like colored printing:
STA = "\x1b["
STO = STA + "0m"
COL = ["31;40m", "36;40m", "32;40m", "35;40m"]


def extract_header(datapath):
    """Simply extract the usefull data from the header"""
    thefile = open(datapath, "r")
    bonusheader = ""
    status = 0
    nrrows = 0
    for k in thefile:
        if k == "\n":
            status = 0
            nrrows += 1
            continue
        if k[:6] == "1     ":
            nrrows += 1
            print("\tLast headerrow found: " + str(nrrows))
            return nrrows
        kk = k.split()
        if kk[0] == "Selected":
            print("\tHeader found, now extracting column names")
            status = 1
        if kk[0] == "Year=" or "Latitude=" or "Prof.":
            bonusheader += k
        if status == 1:
            nr = kk[0]
            name = kk[1][:-1]
            unit = kk[2]
        nrrows += 1


def nrml2psf(datapath):
    """build the psf file
    Pressure is not part of the nrlmsise00 output. We therefore calculate it
    assuming ideal gas conditions. This is support by the relatively low
    densities which negate most deviations from ideal gas law. We also use
    Daltons law of partial pressures to calculate the net pressure.
    """
    rows = extract_header(datapath)
    print("\tStarting processing... " + datapath)
    data = np.loadtxt(datapath, skiprows=rows)
    alt = data[:, 0]
    temp = data[:, 5]
    rho = data[:, 4]
    nN2 = data[:, 2] + 0.5 * data[:, 9]  # molecular + atomic
    nO2 = data[:, 3] + 0.5 * data[:, 1]  # molecular + atomic
    nHe = data[:, 6]
    nAr = data[:, 7]
    nH = data[:, 8]

    # Prepare output array
    nrSheets = data.shape[0]  # one line per sheet
    output = np.zeros((nrSheets, FIRST_ELEMENT + 5))  # Array of zeros
    earthRadius = 6371000  # in meters
    thickness = data[1:, 0] - data[:-1, 0]  # uniform sheet thickness
    thickness *= 1000  # convert to meters
    thickness = np.append(thickness, thickness[-1])
    print("\tAtmospheric thickness: " + str(thickness), 3)
    botAltitudes = earthRadius + alt * 1000
    topAltitudes = botAltitudes + thickness

    # Fill out the pressures
    kb = 1.38064852e-23  # m^2kgs^-2K^-1 -
    pO2 = nO2 * kb * 1000000 * temp  # convert to Pascals
    pN2 = nN2 * kb * 1000000 * temp  # convert to Pascals
    pAr = nAr * kb * 1000000 * temp  # convert to Pascals
    pHe = nHe * kb * 1000000 * temp  # convert to Pascals
    pH = nH * kb * 1000000 * temp  # convert to Pascals
    pTotal = pO2 + pN2 + pAr + pHe + pH

    # Here are the molecular weights
    wO2 = 2 * 15.9994
    wN2 = 2 * 14.0067
    wAr = 39.948
    wHe = 4.0026
    wH = 1.008
    u = 1.66054e-24  # atomic mass unit in g
    mO2 = nO2 * wO2 * u  # mass of oxygen in 1 cm3
    mN2 = nN2 * wN2 * u
    mAr = nAr * wAr * u
    mHe = nHe * wHe * u
    mH = nH * wH * u
    total = mO2 + mN2 + mAr + mHe + mH
    mfO2 = mO2 / total
    mfN2 = mN2 / total
    mfAr = mAr / total
    mfHe = mHe / total
    mfH = mH / total
    # for l in range(nrSheets):

    # we now fill out the output file
    output[:, INNER_RADIUS] = botAltitudes / 1000.0
    output[:, OUTER_RADIUS] = topAltitudes / 1000.0
    output[:, PHI_START] = 0  # dummy
    output[:, PHI_END] += 2 * np.pi  # unit is pi!
    output[:, THETA_START] = 0  # dummy
    output[:, THETA_END] += 1 * np.pi  # unit is pi!
    output[:, DETECTOR_ID] = np.arange(2, nrSheets + 2)
    output[:, TEMPERATURE] = temp
    output[:, DENSITY] = rho
    output[:, PRESSURE] = pTotal
    output[:, STATE] = 0  # dummy
    output[:, FIRST_ELEMENT:] = np.column_stack((mfN2, mfO2, mfAr, mfHe, mfH))

    print("\tCOMPLETE: writing out the gdml lines.")
    formats = ["%e"] * output.shape[1]
    formats[DETECTOR_ID] = "%i"
    formatstring = " ".join(formats)
    np.savetxt(arg1 + ".psf", output, fmt=formatstring)
    # we now read the saved file an add the header, the core, crust and loss
    # volumes.
    f = open(arg1 + ".psf", "r")
    ff = f.readlines()
    f.close()

    cr = 20 / 1000.0  # thickness in kilometers
    er = earthRadius / 1000.0
    top = (topAltitudes[-1] + 1) / 1000.0
    t = 293.15  # temperature in Kelvins
    p = 101325  # pressure in Pascals
    d = 2.7  # density in g/cm3

    def solid_row(inner, outer, detector_id):
        row = np.zeros(output.shape[1])
        row[INNER_RADIUS], row[OUTER_RADIUS] = inner, outer
        row[PHI_END], row[THETA_END] = 2 * np.pi, np.pi
        row[DETECTOR_ID] = detector_id
        row[TEMPERATURE], row[DENSITY], row[PRESSURE] = t, d, p
        row[STATE] = 1
        return formatstring % tuple(row)

    f = open(arg1 + ".psf", "w")
    f.write("#O478Si284Al84Fe52Ca37Na28Mg15 N O Ar He H\n")  # Adding the header file
    f.write(solid_row(0, er - cr, 0))
    f.write("\n")
    f.write(solid_row(er - cr, er, 1))
    f.write("\n")
    for k in ff:
        f.write(k)
    f.write(solid_row(top, top + cr, nrSheets + 2))
    f.write("\n")
    f.close()


if __name__ == "__main__":
    os.system("clear")
    print("\t################################################################")
    print("\t$$                  NRLMSISE00 2 PSF                          $$")
    print("\t################################################################")
    print("\tThis is a simple interface to the NRLMSISE00 model data.")
    print("\tIt generates psf files from the ascii file that can be obtained")
    print("\ton https://ccmc.gsfc.nasa.gov/modelweb/models/nrlmsise00.php.")
    print("\tBecause of the unusual order of the nrlmsise data file, it is")
    print("\trather complicated to build a do-it-all interace. Use this as")
    print("\tan example. Two screenshots sett1.png and sett2.png show what")
    print("\tsettings have been used to generate compatible data. Usage")
    print("\t")
    print("\t\tpython nrlm2psf.py filenameprefix")
    print("\t")
    print("\twhere filenameprefix is the filename without the extension .nrlm")
    print("\t################################################################")
    print("\t################################################################")

    # load data, count the abundance and save the data:
    arg1 = sys.argv[1]
    if os.path.isfile(arg1 + ".nrlm"):
        print("\tNow processing the ascii file: " + arg1 + ".nrlm")
        nrml2psf(arg1 + ".nrlm")
    else:
        print("\tThe file " + arg1 + ".nrlm does not exist.")
