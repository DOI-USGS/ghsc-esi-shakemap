#!/usr/bin/env python

# stdlib imports
import argparse
import json
import os.path
import pathlib
import sys

# local imports
from esi_utils_time.ancient_time import HistoricTime
from shakemap_modules.utils.comcat import get_bytes
from shakemap_modules.utils.config import get_config_paths
from shakemap_modules.utils.smclone import ShakeClone
from shakemap_modules.utils.utils import get_network_name

TIMEFMT2 = "%Y-%m-%dT%H:%M:%S"
KM2SEC = 3600.0 / 111  # seconds per kilometer


def get_parser():
    description = """
    "Clone" a ShakeMap from NEIC Comcat, or create an event from scratch.

    Notes on usage:

    eventid is a ComCat event ID.  For example, for this event:
    https://earthquake.usgs.gov/earthquakes/eventpage/us2000ar20
    The event ID is us2000ar20.

    If no source is specified, then the event ID used for the event directory,
    eventid field in event.xml file, and names of data and fault files will
    be that of the *authoritative* origin.

    If a source (us, ci, nc, etc.) is specified, then that ID is used instead
    of the authoritative ID.


    """
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=description, formatter_class=formatter)
    parser.add_argument("eventid", help="ID of the event to process")
    parser.add_argument(
        "-f", "--force", action="store_true", help="Force overwrite of event data."
    )
    parser.add_argument(
        "-s", "--source", help="Specify the source network of desired shakemap."
    )
    parser.add_argument(
        "-e",
        "--event",
        nargs=7,
        metavar=("NETID", "TIME", "LON", "LAT", "DEP", "MAG", "LOCSTR"),
        help="Specify the event parameters (locstr should " "be in quotes)",
    )
    parser.add_argument(
        "--network", help=("Specify network name " "to be filled in event.xml file")
    )
    parser.add_argument(
        "-b",
        "--skip-bounds",
        action="store_true",
        default=False,
        help="Skip bounds set in online shakemap.",
    )
    parser.add_argument(
        "-m",
        "--get-model",
        action="store_true",
        default=False,
        help=(
            "By default, sm_create will NOT retrieve model.conf "
            "information from ComCat. If used, this flag will "
            "tell sm_create to construct a model.conf file using "
            "the parameters found in `info.json`."
        ),
    )
    parser.add_argument(
        "-n",
        "--no-scenario",
        action="store_true",
        default=False,
        help="When used with -e, disable scenario mode.",
    )
    parser.add_argument(
        "-v",
        "--version-history",
        action="store_true",
        default=False,
        help="Preserve and increment from ShakeMap run version detected in ComCat.",
    )
    return parser


def assemble_event_dict(arg_event, arg_network, arg_eventid, no_scenario):
    locstring = ""
    netid = arg_event[0]
    timestr = arg_event[1]
    # make sure that time string is a valid time format but keep it as a string
    time = HistoricTime.fromisoformat(timestr).strftime(TIMEFMT2)
    lon = float(arg_event[2])
    lat = float(arg_event[3])
    depth = float(arg_event[4])
    mag = float(arg_event[5])
    locstring = arg_event[6]

    # quick check of coordinates
    if lat > 90 or lat < -90:
        print("You seem to have flipped your lon/lat values. Exiting.")
        sys.exit(1)

    if not arg_network:
        network = get_network_name(netid)
    else:
        network = arg_network
    if network == "unknown":
        network = ""

    eventid = arg_eventid
    event_type = "ACTUAL"
    if not no_scenario:
        if not arg_eventid.endswith("_se"):
            eventid = eventid + "_se"
            event_type = "SCENARIO"

    edict = {
        "id": eventid,
        "netid": netid,
        "network": network,
        "time": time,
        "lat": lat,
        "lon": lon,
        "depth": depth,
        "mag": mag,
        "event_type": event_type,
        "locstring": locstring,
    }

    return edict


def main():
    parser = get_parser()
    args = parser.parse_args()

    install_path, data_path = get_config_paths()
    if not os.path.isdir(data_path):
        print(f"{data_path} is not a valid directory.")
        sys.exit(1)

    # get the global config for modules.conf
    module_file = os.path.join(install_path, "config", "modules.conf")

    eventid = args.eventid
    if args.event:
        edict = assemble_event_dict(
            args.event, args.network, args.eventid, args.no_scenario
        )
        eventid = edict["id"]
    else:
        edict = None
    event_path = pathlib.Path(data_path) / eventid / "current"

    if event_path.exists() and not args.force:
        print(
            f"Event directory {event_path} already exists.  Use -f option to overwrite."
        )
        sys.exit(1)

    is_online_scenario = eventid.endswith("_se") and args.event is None
    smclone = ShakeClone(
        eventid,
        event_path,
        source=args.source,
        is_online_scenario=is_online_scenario,
        event_dict=edict,
    )
    get_model = args.get_model
    if args.event is not None and get_model:
        # if we're making a local event from scratch get_model makes no sense
        get_model = False

    get_dyfi = args.event is None
    get_instrumented = args.event is None
    get_macroseismic = args.event is None
    get_rupture = args.event is None
    messages, model_filename = smclone.clone(
        module_file=module_file,
        get_model=get_model,
        skip_bounds=args.skip_bounds,
        get_dyfi=get_dyfi,
        get_instrumented=get_instrumented,
        get_macroseismic=get_macroseismic,
        get_rupture=get_rupture,
        preserve_version_history=args.version_history,
    )
    if len(messages):
        msg = (
            f"**WARNING!!** Some of the modeling values from ComCat were "
            "not found in the list of known modules. The model file has been "
            f"saved as {model_filename}. This WILL NOT be detected by the "
            "shake program. If you want to use this file, you will need to "
            "modify the modeling choices to match known modules and change "
            "the file name to model.conf. The unmatched model name errors follow:\n"
        )
        print(msg)
        for message in messages:
            print(message)
    event_files = list(event_path.glob("*"))
    print(f"Wrote {len(event_files)} files to {event_path}:")
    for event_file in event_files:
        print(f"\t{event_file.name}")


def write_history_json(jsonfile, shakemap):
    url = shakemap["contents"]["download/info.json"]["url"]
    jdict = json.loads(get_bytes(url).decode("utf8"))
    versiondict = jdict["processing"]["shakemap_versions"]["map_data_history"]
    with open(jsonfile, "wt") as f:
        json.dump(versiondict, f)


if __name__ == "__main__":
    main()
