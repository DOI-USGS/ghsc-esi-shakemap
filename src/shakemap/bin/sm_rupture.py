#!/usr/bin/env python
"""
This is a utility program for creating ShakeMap 4 rupture.json files, either
from a ShakeMap 3 style *_fault.txt file (and optionally an event.xml file),
or the program will prompt you to manually input rupture data (strike, dip,
length, ...).
"""

import argparse
import copy

import numpy as np
from esi_utils_rupture.factory import get_rupture
from esi_utils_rupture.origin import Origin
from esi_utils_rupture.quad_rupture import QuadRupture


# Lame method to detect integer using try block because
# python doesn't have this basic function.
def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def prompt_user(args, origin):
    ref = input("  - Rupture reference? ")
    origin.reference = ref

    n_quad = input("  - How many quadrilaterals are in this rupture? ")
    if is_int(n_quad):
        n_quad = int(n_quad)
    else:
        raise ValueError("Number of quadrilaterals must be an interger.")

    px = []
    py = []
    pz = []
    dx = []
    dy = []
    length = []
    width = []
    strike = []
    dip = []
    for i in range(n_quad):
        print(f"  Quad {i + 1} of {n_quad}...")

        out = input("    Longitude of known point: ")
        if is_float(out):
            px.append(float(out))
        else:
            raise ValueError("Longitude of known point must be a float.")

        out = input("    Latitude of known point: ")
        if is_float(out):
            py.append(float(out))
        else:
            raise ValueError("Latitude of known point must be a float.")

        out = input("    Depth (km) of known point: ")
        if is_float(out):
            pz.append(float(out))
        else:
            raise ValueError("Depth of known point must be a float.")

        out = input("    Along-strike distance (km) of known point: ")
        if is_float(out):
            dx.append(float(out))
        else:
            raise ValueError("Distance must be a float.")

        out = input("    Along-dip distance (km) of known point: ")
        if is_float(out):
            dy.append(float(out))
        else:
            raise ValueError("Distance must be a float.")

        out = input("    Length (km) of quadrilateral: ")
        if is_float(out):
            length.append(float(out))
        else:
            raise ValueError("Length must be a float.")

        out = input("    Width (km) of quadrilateral: ")
        if is_float(out):
            width.append(float(out))
        else:
            raise ValueError("Width must be a float.")

        out = input("    Strike (deg) of quadrilateral: ")
        if is_float(out):
            strike.append(float(out))
        else:
            raise ValueError("Strike must be a float.")

        out = input("    Dip (deg) of quadrilateral: ")
        if is_float(out):
            dip.append(float(out))
        else:
            raise ValueError("Dip must be a float.")

    return QuadRupture.fromOrientation(
        px, py, pz, dx, dy, length, width, strike, dip, origin
    )


def main():
    """ """
    parser = get_parser()
    args = parser.parse_args()
    # First deal with origin
    if args.eventfile:
        origin = Origin.fromFile(args.eventfile)
    else:
        print("* No event.xml file specified, using dummy origin...")
        dummy = {
            "mag": "",
            "id": "",
            "mech": "",
            "lon": np.nan,
            "lat": np.nan,
            "depth": "",
            "locstring": "",
            "netid": "",
            "network": "",
            "time": "",
        }
        origin = Origin(dummy)

    # Was a fault file given?
    if args.file:
        # User provided fault.txt file
        rup = get_rupture(origin, file=args.file, new_format=not args.old)
    else:
        # User did not provide fault.txt file
        explain_text = """
* No fault file specified. You will be prompted to manually enter rupture
information.

You will need to specify the number of quadrilaterals in the rupture. Each
quadrilateral will be defined with the following geometry:

                            strike direction
                        p1*------------------->>p2
                        *        | dy           |
                 dip    |--------o              |
              direction |   dx    known point   | Width
                        V                       |
                        V                       |
                        p4----------------------p3
                                Length
"""
        print(explain_text)
        rup = prompt_user(args, origin)

    # Remove any blank or nan origin info
    odict = copy.copy(rup._origin.__dict__)
    for k, v in odict.items():
        if isinstance(v, str):
            if not v:
                rup._geojson["metadata"].pop(k, None)
        if isinstance(v, float):
            if np.isnan(v):
                rup._geojson["metadata"].pop(k, None)

    # Write output
    rup.writeGeoJson(args.outfile)


def get_parser():
    desc = """Create a ShakeMap 4 Rupture File.

This program creates a ShakeMap 4 rupture file. If a ShakeMap 3 *_fault.txt
file is provided, it will try to convert it to a rupture.json file. Otherwise,
the user will be prompted to manually input rupture data (strike, dip, ...).

Note that the rupture.json requires some origin information that is not in
the fault.txt file and so these values are filled in with empty values unless
an event.xml file is also provided.
"""
    parser = argparse.ArgumentParser(description=desc, epilog="\n\n")
    parser.add_argument("outfile", help="Path for output rupture file.")
    parser.add_argument("-f", "--file", type=str, help="Path to ShakeMap 3 fault file.")
    parser.add_argument(
        "-e", "--eventfile", type=str, help="Path to an event.xml file."
    )
    parser.add_argument(
        "-o",
        "--old",
        action="store_true",
        help="Indicates that the ShakeMap 3 fault file"
        "uses the old format (ordering lon before "
        "lat).",
    )
    return parser


if __name__ == "__main__":
    main()
