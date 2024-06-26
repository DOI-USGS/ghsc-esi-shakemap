#!/usr/bin/env python

# stdlib imports
import argparse
from urllib.parse import urlparse
import os.path
import sys
import re

# local imports
from shakemap_modules.utils.config import get_config_paths
from shakemap_modules.coremods.dyfi import _get_dyfi_dataframe
from shakemap_modules.utils.dataframe import dataframe_to_xml

DETAIL_TEMPLATE = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?" "eventid=[EID]&format=geojson"
)

URL_REGEX = re.compile(
    r"^(?:http|ftp)s?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|"
    "[A-Z0-9-]{2,}\.?)|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


def get_parser():
    description = """
    Download DYFI data from a file NEIC Comcat into a local data directory.

    Where url_or_id is a ComCat event page URL or event ID.
    For example, the url for the 2014 South Napa event is:
    https://earthquake.usgs.gov/earthquakes/eventpage/nc72282711
    and the event ID is nc72282711.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("url_or_id", help="ComCat URL/ID of the event to process")
    parser.add_argument("--inputfile", help="Use file instead of loading from ComCat")
    parser.add_argument("--file", help="Download to Excel file specified")
    parser.add_argument(
        "--keepstddev", help="Don't recompute DYFI stddev", action="store_true"
    )
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    install_path, data_path = get_config_paths()
    if not os.path.isdir(data_path):
        print(f"{data_path} is not a valid directory.")
        sys.exit(1)

    rerun_stddev = not args.keepstddev

    # is this an event ID or a url?
    is_url = re.match(URL_REGEX, args.url_or_id) is not None
    if is_url:
        if args.inputfile:
            print("Cannot use inputfile with ComCat URL")
            sys.exit(0)

        dataframe, msg = _get_dyfi_dataframe(args.url_or_id, rerun_stddev=rerun_stddev)

        # get the eventid from the url
        parts = urlparse(args.url_or_id)
        eventid = parts.path.split("/")[-1]

    # if not, check if inputfile provided
    elif args.inputfile:
        eventid = args.url_or_id
        dataframe, msg = _get_dyfi_dataframe(
            None, args.inputfile, rerun_stddev=rerun_stddev
        )

    # if not, load URL
    else:
        eventid = args.url_or_id
        detail_url = DETAIL_TEMPLATE.replace("[EID]", eventid)
        dataframe, msg = _get_dyfi_dataframe(detail_url, rerun_stddev=rerun_stddev)

    if dataframe is None:
        print(msg)
        print("No DYFI data found, exiting.")
        sys.exit(0)

    if args.file:
        dataframe.to_excel(args.file, index=False)
        print("Saved %i records to %s. Exiting." % (len(dataframe), args.file))
        sys.exit(0)

    # check to see if the event directory exists
    event_dir = os.path.join(data_path, eventid, "current")
    if not os.path.isdir(event_dir):
        fmt = (
            "Event %s does not exist in this installation.  Run "
            '"sm_create %s" first.'
        )
        print(fmt % (eventid, eventid))
        sys.exit(1)

    reference = "USGS Did You Feel It? System"
    outfile = os.path.join(event_dir, "dyfi_dat.xml")
    dataframe_to_xml(dataframe, outfile, reference)
    print(f"Saved DYFI data to {outfile}.")
    sys.exit(0)


if __name__ == "__main__":
    main()
