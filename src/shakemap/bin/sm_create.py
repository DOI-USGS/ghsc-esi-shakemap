#!/usr/bin/env python

# stdlib imports
import argparse
import copy
import datetime
import json
import os.path
import pathlib
import re
import shutil
import sys
import warnings
from collections import OrderedDict
from xml.sax import make_parser
from xml.sax.handler import ContentHandler
from configobj import ConfigObj

# third party imports
import numpy as np

# local imports
from esi_utils_rupture.factory import get_rupture
from esi_utils_rupture.origin import Origin, write_event_file
from esi_utils_time.ancient_time import HistoricTime
from esi_shakelib.station import StationList
from shakemap_modules.coremods.dyfi import _get_dyfi_dataframe
from shakemap_modules.utils.comcat import get_bytes, get_detail_json
from shakemap_modules.utils.config import (
    config_error,
    get_config_paths,
    get_configspec,
    get_custom_validator,
)
from shakemap_modules.utils.dataframe import dataframe_to_xml
from shakemap_modules.utils.layers import update_config_regions, validate_config
from shakemap_modules.utils.probs import get_weights
from shakemap_modules.utils.utils import get_network_name, migrate_gmpe, set_gmpe

TIMEFMT2 = "%Y-%m-%dT%H:%M:%S"
KM2SEC = 3600.0 / 111  # seconds per kilometer


def get_shakemap_from_source(detail, ptype, source):
    auth_product = None
    auth_time = 0
    if source == "preferred":
        auth_product = detail["properties"]["products"][ptype][0]
    else:
        for product in detail["properties"]["products"][ptype]:
            if product["source"] != source:
                continue
            if product["updateTime"] > auth_time:
                auth_time = product["updateTime"]
                auth_product = product
    return auth_product


def validate_xml(xmlfile):
    parser = make_parser()
    parser.setContentHandler(ContentHandler())
    try:
        parser.parse(xmlfile)
        return True
    except Exception:
        return False
    return False


def validate_json(jsonfile):
    try:
        with open(jsonfile, "rt") as fh:
            _ = json.load(fh)
        return True
    except Exception:
        return False


def write_instrumented(data_file, event_dir):
    # load the file, nuke any data not from an instrument
    instrumented = StationList.loadFromFiles([data_file])
    db = instrumented.db
    cursor = instrumented.cursor
    cursor.execute("SELECT count(*) FROM station")
    nrows = cursor.fetchone()[0]
    # sys.stderr.write('Original data set had %i total stations.\n' % nrows)
    query1 = "SELECT id FROM station WHERE instrumented != 1"
    cursor.execute(query1)
    srows = cursor.fetchall()
    for srow in srows:
        sid = srow[0]
        query2 = f'DELETE FROM amp WHERE station_id="{sid}"'
        cursor.execute(query2)
        db.commit()
        query3 = f'DELETE FROM station WHERE id="{sid}"'
        cursor.execute(query3)
        db.commit()

    cursor.execute("SELECT count(*) FROM station")
    nrows = cursor.fetchone()[0]
    instrument_file = None
    if nrows:
        jsonstr = instrumented.getGeoJson()
        instrument_file = os.path.join(event_dir, "instrumented_dat.json")
        with open(instrument_file, "wt") as f:
            json.dump(jsonstr, f)
    return instrument_file


def write_macroseismic(data_file, event_dir):
    # load the file, nuke any data that is not macroseismic
    macroseismic = StationList.loadFromFiles([data_file])
    db = macroseismic.db
    cursor = macroseismic.cursor
    cursor.execute("SELECT count(*) FROM station")
    nrows = cursor.fetchone()[0]
    # sys.stderr.write('Original data set had %i total stations.\n' % nrows)
    # first remove instruments
    query1 = "SELECT id FROM station WHERE instrumented == 1"
    cursor.execute(query1)
    srows = cursor.fetchall()
    for srow in srows:
        sid = srow[0]
        query2 = f'DELETE FROM amp WHERE station_id="{sid}"'
        cursor.execute(query2)
        db.commit()
        query3 = f'DELETE FROM station WHERE id="{sid}"'
        cursor.execute(query3)
        db.commit()
    # next, remove DYFI
    query4 = 'SELECT id FROM station WHERE network in ("DYFI", "CIIM")'
    cursor.execute(query4)
    srows = cursor.fetchall()
    for srow in srows:
        sid = srow[0]
        query5 = f'DELETE FROM amp WHERE station_id="{sid}"'
        cursor.execute(query5)
        db.commit()
        query6 = f'DELETE FROM station WHERE id="{sid}"'
        cursor.execute(query6)
        db.commit()
    cursor.execute("SELECT count(*) FROM station")
    nrows = cursor.fetchone()[0]
    macro_file = None
    if nrows:
        jsonstr = macroseismic.getGeoJson()
        macro_file = os.path.join(event_dir, "macroseismic_dat.json")
        with open(macro_file, "wt") as f:
            json.dump(jsonstr, f)

    return macro_file


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
        "-n",
        "--no-scenario",
        action="store_true",
        default=False,
        help="When used with -e, disable scenario mode.",
    )
    parser.add_argument(
        "-p",
        "--preserve-params",
        action="store_true",
        default=False,
        help="Preserve model parameters detected in ComCat. Should only be "
        "used on ShakeMap 3.5 products",
    )
    parser.add_argument(
        "-v",
        "--version-history",
        action="store_true",
        default=False,
        help="Preserve and increment from ShakeMap run version detected in ComCat.",
    )
    return parser


def _get_event_dictionary(detail, source, scenario):
    # get basic event information from an origin contributed by input
    # source
    edict = None
    eventid = detail["id"]
    lon, lat, depth = detail["geometry"]["coordinates"]
    time = datetime.datetime.fromtimestamp(detail["properties"]["time"] / 1000)
    if source is not None:
        try:
            edict = {
                "id": eventid,
                "netid": source,
                "network": get_network_name(source),
                "lat": lat,
                "lon": lon,
                "depth": depth,
                "mag": detail["properties"]["mag"],
                "time": time,
                "locstring": detail["properties"]["place"],
                "event_type": "ACTUAL",
            }
        except ValueError:
            print(f"No origin for event {source}.")
    else:  # no source specified, use detail object
        if scenario is True:
            netname = detail["properties"]["net"]
            etype = "SCENARIO"
        else:
            netname = get_network_name(detail["properties"]["net"])
            etype = "ACTUAL"
        edict = {
            "id": eventid,
            "netid": detail["properties"]["net"],
            "network": netname,
            "lat": lat,
            "lon": lon,
            "depth": depth,
            "mag": detail["properties"]["mag"],
            "time": time,
            "locstring": detail["properties"]["place"],
            "event_type": etype,
        }
    if edict["locstring"] is None:
        edict["locstring"] = ""
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
    module_conf = ConfigObj(module_file)

    # get the global config for migrate.conf
    migrate_file = os.path.join(install_path, "config", "migrate.conf")
    spec_file = get_configspec("migrate").as_posix()
    validator = get_custom_validator()
    migrate_conf = ConfigObj(migrate_file, configspec=spec_file)
    results = migrate_conf.validate(validator)
    if not isinstance(results, bool) or not results:
        config_error(migrate_conf, results)

    if args.event:
        locstring = ""
        netid = args.event[0]
        timestr = args.event[1]
        time = HistoricTime.strptime(timestr, TIMEFMT2)
        lon = float(args.event[2])
        lat = float(args.event[3])
        depth = float(args.event[4])
        mag = float(args.event[5])
        locstring = args.event[6]

        # quick check of coordinates
        if lat > 90 or lat < -90:
            print("You seem to have flipped your lon/lat values. Exiting.")
            sys.exit(1)

        if not args.network:
            network = get_network_name(netid)
        else:
            network = args.network
        if network == "unknown":
            network = ""

        eventid = args.eventid
        event_type = "ACTUAL"
        if not args.no_scenario:
            if not args.eventid.endswith("_se"):
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
        detail = None
    else:
        # Get the DetailEvent product for this event ID
        # regardless of input, the output directory and files
        # will contain the *authoritative* event ID from ComCat,
        # unless source is specified.
        if args.eventid.endswith("_se"):
            scenario = True
        else:
            scenario = False
        try:
            detail = get_detail_json(args.eventid, scenario=scenario)
        except Exception:
            expected_url = (
                "https://earthquake.usgs.gov/earthquakes"
                f"/eventpage/{args.eventid}/executive"
            )
            msg = (
                f"\nWe were unable to validate that {args.eventid} is a valid\n"
                "event ID in ComCat. The expected URL for that\n"
                f"event ID would be:\n\n{expected_url}\n\n"
                "Please check that this web page exists.\n"
            )
            print(msg)
            sys.exit(1)
        # get input data
        edict = _get_event_dictionary(detail, args.source, scenario)
        if edict is None:
            print("No event dictionary, quitting.")
            exit(1)
        eventid = edict["id"]

    # check to see if the event directory exists
    event_dir = os.path.join(data_path, eventid, "current")
    if not os.path.isdir(event_dir):
        os.makedirs(event_dir)
    else:
        if not args.force:
            print(
                "Event directory %s already exists.  Use -f "
                "option to overwrite." % event_dir
            )
            sys.exit(1)
        shutil.rmtree(event_dir)
        os.makedirs(event_dir)

    # name the event.xml file
    event_xml_file = os.path.join(event_dir, "event.xml")

    # write the event.xml file
    write_event_file(edict, event_xml_file)

    if detail is not None:
        has_shakemap = "shakemap" in detail["properties"]["products"]
        has_scenario = "shakemap-scenario" in detail["properties"]["products"]
        has_dyfi = "dyfi" in detail["properties"]["products"]
        # if this event has a shakemap, then we have more to do
        if (scenario is False and not has_shakemap) or (
            scenario is True and not has_scenario
        ):
            if not has_dyfi:
                print(
                    "Event %s has no ShakeMap product. "
                    "Creating a basic ShakeMap." % detail["id"]
                )
            else:
                print(
                    "Event %s has no ShakeMap product, but does have DYFI. "
                    "Downloading that data." % detail["id"]
                )
                dataframe, msg = _get_dyfi_dataframe(detail)
                if dataframe is not None and len(dataframe):
                    data_file = os.path.join(event_dir, "dyfi_dat.xml")
                    reference = "USGS Did You Feel It? System"
                    dataframe_to_xml(dataframe, data_file, reference)
        else:
            if args.source:
                source = args.source
            else:
                source = "preferred"
            try:
                if scenario is True:
                    shakemap = get_shakemap_from_source(
                        detail, "shakemap-scenario", source
                    )
                else:
                    shakemap = get_shakemap_from_source(detail, "shakemap", source)
            except AttributeError:
                msg = f"No ShakeMap product from source {source} exists."
                print(msg)
                sys.exit(0)

            got_data_file = False
            # reg = re.compile(r'^x')                    # Compile the regex
            # test = list(filter(reg.search, test))
            xml_regex = re.compile("stationlist.xml")
            json_regex = re.compile("stationlist.json")
            xml_match = list(
                filter(xml_regex.search, list(shakemap["contents"].keys()))
            )
            json_match = list(
                filter(json_regex.search, list(shakemap["contents"].keys()))
            )
            key = None
            # prefer json over xml
            if len(xml_match):
                key = xml_match[0]
                data_file = os.path.join(event_dir, f"{eventid}_dat.xml")
                validate_fxn = validate_xml
            if len(json_match):
                key = json_match[0]
                data_file = os.path.join(event_dir, f"{eventid}_dat.json")
                validate_fxn = validate_json
            if key is None:
                print("No station data found. Continuing.")
            else:
                url = shakemap["contents"][key]["url"]
                bytes = get_bytes(url)
                with open(data_file, "wb") as f:
                    f.write(bytes)
                got_data_file = True
                if not validate_fxn(data_file):
                    os.remove(data_file)
                    got_data_file = False

            if got_data_file:
                _ = write_instrumented(data_file, event_dir)
                _ = write_macroseismic(data_file, event_dir)
                os.remove(data_file)
            else:
                fmt = (
                    "Error while attempting to download ShakeMap ground "
                    "motion data file."
                )
                print(fmt)

            # let's try to write out the input data in as many as three files:
            # 1) dyfi_dat.xml, the most up to date DYFI we have.
            # 2) instrumented_dat.son, all of the instrumented data from
            #    stationlist.xml
            # 3) macroseismic_dat.json, all of the macroseismic data from
            #    stationlist.xml
            dataframe, msg = _get_dyfi_dataframe(detail)
            if dataframe is not None:
                dyfi_file = os.path.join(event_dir, "dyfi_dat.xml")
                reference = "USGS Did You Feel It? System"
                dataframe_to_xml(dataframe, dyfi_file, reference)

            json_regex = re.compile("rupture.json")
            text_regex = re.compile("fault.txt")
            json_fault_files = list(
                filter(json_regex.search, list(shakemap["contents"].keys()))
            )
            text_fault_files = list(
                filter(text_regex.search, list(shakemap["contents"].keys()))
            )
            fault_files = []
            origin = None
            if len(json_fault_files):
                fault_files = json_fault_files
            elif len(text_fault_files):
                fault_files = text_fault_files
                origin = Origin.fromFile(event_xml_file)
            if len(fault_files):
                key = fault_files[0]
                fname = pathlib.Path(key).name
                fault_file = os.path.join(event_dir, fname)
                url = shakemap["contents"][key]["url"]
                bytes = get_bytes(url)

                with open(fault_file, "wb") as f:
                    f.write(bytes)

                if origin is not None:
                    try:
                        rupt = get_rupture(origin, file=fault_file, new_format=False)
                        # Remove any blank or nan origin info
                        odict = copy.copy(rupt._origin.__dict__)
                        for k, v in odict.items():
                            if isinstance(v, str):
                                if not v:
                                    rupt._geojson["metadata"].pop(k, None)
                            if isinstance(v, float):
                                if np.isnan(v):
                                    rupt._geojson["metadata"].pop(k, None)

                        jsonfile = os.path.join(event_dir, "rupture.json")
                        rupt.writeGeoJson(jsonfile)
                        os.remove(fault_file)

                    except Exception as e:
                        msg = (
                            "WARNING: UNABLE TO PARSE FAULT TEXT FILE. "
                            "ERROR: \n\n%s\n\n"
                            "The following text file has been left in place "
                            "for you to edit manually:\n\n%s\n"
                        )

                        errmsg = str(e)
                        print(msg % (errmsg, fault_file))

            if args.version_history:
                jsonfile = event_xml_file = os.path.join(event_dir, "history.json")
                write_history_json(jsonfile, shakemap)

            # if the user wanted to preserve the model parameters found
            # in info.json, set those here
            if args.preserve_params:
                _write_model_conf(
                    shakemap,
                    module_conf,
                    migrate_conf,
                    event_dir,
                    skip_bounds=args.skip_bounds,
                )
            else:
                model = ConfigObj(indent_type="    ")
                install_path, data_path = get_config_paths()
                config = ConfigObj(os.path.join(install_path, "config", "select.conf"))
                global_data_path = os.path.join(
                    os.path.expanduser("~"), "shakemap_data"
                )
                validate_config(config, install_path, data_path, global_data_path)
                org = Origin(edict)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    config = update_config_regions(org.lat, org.lon, config)
                if scenario is True:
                    org.id = None
                gmm_dict, strec_results = get_weights(org, config)
                gmpe_set = "gmpe_" + edict["id"] + "_custom"
                model["gmpe_sets"] = OrderedDict(
                    [
                        (
                            gmpe_set,
                            OrderedDict(
                                [
                                    ("gmpes", list(gmm_dict["gmpelist"])),
                                    ("weights", list(gmm_dict["weightlist"])),
                                    ("weights_large_dist", "None"),
                                    ("dist_cutoff", "nan"),
                                    ("site_gmpes", "None"),
                                    ("weights_site_gmpes", "None"),
                                ]
                            ),
                        )
                    ]
                )
                model["modeling"] = {}
                model["modeling"]["gmpe"] = gmpe_set
                model["modeling"]["mechanism"] = strec_results["FocalMechanism"]
                if gmm_dict["ipe"]:
                    model["modeling"]["ipe"] = gmm_dict["ipe"]
                if gmm_dict["gmice"]:
                    model["modeling"]["gmice"] = gmm_dict["gmice"]
                if gmm_dict["ccf"]:
                    model["modeling"]["ccf"] = gmm_dict["ccf"]
                model_file = os.path.join(event_dir, "model_select.conf")
                model.filename = model_file
                model.write()

    print("Wrote %i files to %s" % (len(os.listdir(event_dir)), event_dir))


def write_history_json(jsonfile, shakemap):
    url = shakemap["contents"]["download/info.json"]["url"]
    jdict = json.loads(get_bytes(url).decode("utf8"))
    versiondict = jdict["processing"]["shakemap_versions"]["map_data_history"]
    with open(jsonfile, "wt") as f:
        json.dump(versiondict, f)


def _write_model_conf(
    shakemap, module_conf, migrate_conf, event_dir, skip_bounds=False
):
    info_url = shakemap["contents"]["download/info.json"]["url"]
    info_json = get_bytes(info_url)
    info_json = info_json.decode("utf-8")
    jsondict = json.loads(info_json)
    eventid = jsondict["input"]["event_information"]["event_id"]
    model = ConfigObj(indent_type="  ")

    model["modeling"] = {"bias": {}}
    misc_dict = jsondict["processing"]["miscellaneous"]
    bias_max_mag = float(misc_dict["bias_max_mag"])
    max_range = float(misc_dict["bias_max_range"])
    if bias_max_mag > 0 and max_range > 0:
        model["modeling"]["bias"]["do_bias"] = True
        model["modeling"]["bias"]["max_range"] = max_range
        model["modeling"]["bias"]["max_mag"] = bias_max_mag
    else:
        model["modeling"]["bias"]["do_bias"] = False

    # get the outlier information
    model["data"] = {"outlier": {}}
    max_deviation = float(misc_dict["outlier_deviation_level"])
    outlier_max_mag = float(misc_dict["outlier_max_mag"])
    if outlier_max_mag > 0 and max_deviation > 0:
        model["data"]["outlier"]["do_outlier"] = True
        model["data"]["outlier"]["max_deviation"] = max_deviation
        model["data"]["outlier"]["max_mag"] = outlier_max_mag
    else:
        model["data"]["outlier"]["do_outlier"] = False

    # set the gmice in model.conf
    allowed_gmice = module_conf["gmice_modules"].keys()
    gmm_dict = jsondict["processing"]["ground_motion_modules"]
    if "mi2pgm" in gmm_dict:
        gmice = gmm_dict["mi2pgm"]["module"]
    else:
        gmice = gmm_dict["gmice"]["module"]
    # WGRW11 in SM3.5 is WGRW12 in SM4.0
    if gmice == "WGRW11":
        gmice = "WGRW12"
    if gmice not in allowed_gmice:
        # If not implemented, then it will fall back on global conf GMICE
        warnings.warn(
            f"GMICE {gmice} (event {eventid}) not yet supported in ShakeMap 4."
        )
    else:
        model["modeling"]["gmice"] = gmice

    # set the gmpe in model.conf
    old_gmpe = gmm_dict["gmpe"]["module"]
    try:
        new_gmpe, reference = migrate_gmpe(old_gmpe, config=migrate_conf)
        model = set_gmpe(new_gmpe, model, eventid)
    except KeyError:
        old_gmpe = jsondict["multigmpe"]["PGV"]  # all the metrics are the same
        gmpe_name = old_gmpe["name"]
        gmpe_list = old_gmpe["gmpes"][0]["gmpes"]
        gmpe_list = [re.sub(r"\[|\]", "", gmpe) for gmpe in gmpe_list]
        weights = old_gmpe["gmpes"][0]["weights"]
        gmpe_set = {
            "gmpes": gmpe_list,
            "weights": weights,
            "weights_large_dist": None,
            "dist_cutoff": np.nan,
            "site_gmpes": None,
            "weights_site_gmpes": None,
        }
        model["gmpe_sets"] = {gmpe_name: gmpe_set}

    # work on map extent/resolution data
    if not skip_bounds:
        model["interp"] = {"prediction_location": {}}
        map_dict = jsondict["output"]["map_information"]
        yres_km = float(map_dict["grid_spacing"]["latitude"])
        yres_sec = int(round(yres_km * KM2SEC))
        model["interp"]["prediction_location"]["xres"] = "%ic" % yres_sec
        model["interp"]["prediction_location"]["yres"] = "%ic" % yres_sec

        model["extent"] = {"bounds": {}}
        xmin = map_dict["min"]["longitude"]
        xmax = map_dict["max"]["longitude"]
        ymin = map_dict["min"]["latitude"]
        ymax = map_dict["max"]["latitude"]
        model["extent"]["bounds"]["extent"] = [xmin, ymin, xmax, ymax]

    # done with model.conf, merge with existing file and save
    model_file = os.path.join(event_dir, "model.conf")
    if os.path.isfile(model_file):
        existing_model = ConfigObj(model_file)
        model.merge(existing_model)
    model.filename = model_file
    model.write()


if __name__ == "__main__":
    main()
