#!/usr/bin/env python

# stdlib imports
import argparse
import json
import logging
import pathlib
import sys

# third party imports
import h5py
import pandas as pd
import requests
from obspy.clients.fdsn.client import Client
from obspy.clients.fdsn.header import URL_MAPPINGS, FDSNNoDataException
from obspy.core import UTCDateTime

# local imports
from shakemap_modules.utils.config import get_config_paths

START_TIME = UTCDateTime.now()
END_TIME = UTCDateTime.now()

LOGLEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

CESMD_URL = (
    "https://www.strongmotioncenter.org/wserv/stations/query?"
    "netid=CE&sttype=G&minlat={minlat}&maxlat={maxlat}&minlon={minlon}&"
    "maxlon={maxlon}&format=json&nodata=404"
)


def get_cali_stations(bounds):
    xmin, xmax, ymin, ymax = bounds
    url = CESMD_URL.format(minlat=ymin, maxlat=ymax, minlon=xmin, maxlon=xmax)
    response = requests.get(url)
    jdict = response.json()
    rows = []
    for feature in jdict["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        code = feature["properties"]["code"]
        network = feature["properties"]["network"]
        row = (f"{network}.{code}", lat, lon)
        rows.append(row)
    return rows


def get_bounds(datadir):
    result_file = datadir / "products" / "shake_result.hdf"
    with h5py.File(result_file, "r") as fobj:
        jstring = fobj["dictionaries"]["info.json"][()].decode("utf8")
        jdict = json.loads(jstring)
    xmin = float(jdict["output"]["map_information"]["min"]["longitude"])
    xmax = float(jdict["output"]["map_information"]["max"]["longitude"])
    ymin = float(jdict["output"]["map_information"]["min"]["latitude"])
    ymax = float(jdict["output"]["map_information"]["max"]["latitude"])
    return (xmin, xmax, ymin, ymax)


def get_station_frame(bounds):
    station_rows = get_cali_stations(bounds)
    xmin, xmax, ymin, ymax = bounds
    skip_clients = ["EMSC", "IESDMC", "IRISPH5", "ISC", "RESIFPH5", "USGS"]

    for client_code in URL_MAPPINGS.keys():
        if client_code in skip_clients:
            continue
        try:
            client = Client(client_code)
            if "station" not in client.services:
                logging.debug(
                    f"Skipping client {client_code} (doesn't support station search)"
                )
                skip_clients.append(client_code)
                continue
            inventory = client.get_stations(
                network="*",
                station="*",
                channel="HN*",
                startbefore=START_TIME,
                endafter=END_TIME,
                level="channel",
                minlatitude=ymin,
                maxlatitude=ymax,
                minlongitude=xmin,
                maxlongitude=xmax,
            )
            for network in inventory.networks:
                for station in network.stations:
                    row = (
                        f"{network.code}.{station.code}",
                        station.latitude,
                        station.longitude,
                    )
                    station_rows.append(row)
        except FDSNNoDataException as fe:
            logging.debug(f"Skipping client {client_code} because no data was found.")
            continue
        except Exception as fe:
            logging.debug(
                f"Skipping client {client_code} because of some other error {str(fe)}."
            )
            skip_clients.append(client_code)
            continue

    # print(skip_clients)
    stations = pd.DataFrame(data=station_rows, columns=["id", "lat", "lon"])
    # some fdsn services will duplicate station data, remove duplicates here
    stations.drop_duplicates(subset=["id"], inplace=True)
    return stations


def get_stationlist_dataframe(jdata):
    station_rows = []
    for station in jdata["features"]:
        props = station["properties"]
        if props["station_type"] != "seismic":
            continue
        row = (
            station["id"],
            station["geometry"]["coordinates"][1],
            station["geometry"]["coordinates"][0],
            props["vs30"],
        )
        station_rows.append(row)

    stations = pd.DataFrame(data=station_rows, columns=["id", "lat", "lon", "vs30"])
    return stations


def main():
    help = (
        "Create a ShakeMap points 'facilities' file by either using "
        "the bounding box of the input ShakeMap event to retrieve "
        "names and locations of strong motion stations inside that "
        "bounding box (from FDSN servers), or by providing the "
        "location of a stationlist.json file from an existing event. "
        "This program will create the 'input_points.csv' file in the input "
        "event folder suitable for 'points' mode usage of ShakeMap."
        "\n\n"
        "Sample Usage - Create a scenario event based on this event: \n"
        "https://earthquake.usgs.gov/earthquakes/eventpage/nc73292360/executive\n"
        "sm_create tres_pinos_se -s us -e us 2023-12-19T12:00:00 -121.274 36.646 5.0 6.5 'Tres Pinos Scenario'\n"
        "shake tres_pinos_se select assemble -c'test' model mapping\n\n"
        "To retrieve stations based on ShakeMap bounds:\n"
        "se_stations tres_pinos_se -b\n\n"
        "To retrieve the stations used in the M4.7 source event (US ShakeMap):\n"
        "se_stations.py tres_pinos_se -s https://earthquake.usgs.gov/product/shakemap/nc73292360/us/1573711339523/download/stationlist.json"
    )
    parser = argparse.ArgumentParser(
        description=help, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "eventid",
        metavar="EVENTID",
        help="Event where facilities point file should be written.",
    )
    arg_group = parser.add_mutually_exclusive_group()
    arg_group.add_argument(
        "-b",
        "--use-bounds",
        action="store_true",
        default=False,
        help="Use the bounds from the input event ID",
    )
    arg_group.add_argument(
        "-s",
        "--use-stations",
        metavar="STATIONLIST_FILE_OR_URL",
        help="Use a stationlist file OR url as input",
    )

    parser.add_argument(
        "-l", "--loglevel", choices=list(LOGLEVELS.keys()), default="INFO"
    )

    args = parser.parse_args()
    logging.basicConfig(
        encoding="utf-8",
        level=LOGLEVELS[args.loglevel],
        format="%(levelname)s:%(message)s",
    )

    _, data_path = get_config_paths()
    datadir = pathlib.Path(data_path) / args.eventid / "current"
    if not datadir.exists():
        raise FileNotFoundError(f"Input event {args.eventid} not found at {datadir}")
    if args.use_bounds:
        bounds = get_bounds(datadir)
        stationframe = get_station_frame(bounds)
    elif args.use_stations is not None:
        file_or_url = args.use_stations
        station_file = pathlib.Path(file_or_url)
        if not station_file.exists():
            response = requests.get(file_or_url)
            if response.status_code not in [200, 204]:
                msg = (
                    f"{file_or_url} does not exist as a file on this system "
                    "or as a valid url. Exiting."
                )
                print(msg)
                sys.exit(1)
            jdict = response.json()
        else:
            with open(station_file, "rt") as f:
                jdict = json.load(f)
        stationframe = get_stationlist_dataframe(jdict)
    if len(stationframe):
        data_file = datadir / "input_points.csv"
        stationframe.to_csv(data_file, index=False)
        print(f"{len(stationframe)} stations written to {data_file}.")
    else:
        print("No stations were found from any known networks.")
        sys.exit(0)


if __name__ == "__main__":
    main()
