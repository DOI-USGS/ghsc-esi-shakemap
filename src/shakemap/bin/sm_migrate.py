#!/usr/bin/env python

# stdlib imports
import argparse
import glob
import json
import logging
import os.path
import re
import sys
import tarfile
from collections import OrderedDict
from configobj import ConfigObj


# third party imports
import numpy as np

# local imports
from esi_utils_rupture import constants
from esi_utils_rupture.factory import (
    get_rupture,
    rupture_from_dict_and_origin,
    text_to_json,
)
from esi_utils_rupture.origin import Origin, read_event_file, write_event_file
from esi_utils_time.ancient_time import HistoricTime
from esi_shakelib.modules.utils import get_extent
from shakemap_modules.utils.config import (
    config_error,
    get_config_paths,
    get_configspec,
    get_custom_validator,
)
from shakemap_modules.utils.layers import update_config_regions, validate_config
from shakemap_modules.utils.probs import get_weights
from shakemap_modules.utils.utils import get_network_name, migrate_gmpe, set_gmpe

KM2SEC = 3600.0 / 111  # seconds per kilometer


def get_parser():
    description = """Migrate existing ShakeMap 3.5 data directories.

    This program takes one required file, a tarball of one or more ShakeMap 3.5
    event directories.  To create this file, run a command like this:

    find . -maxdepth 3 -name "*_dat.xml" -o -name "*_fault.txt" -o -name
    "source.txt" -o -name "info.json" -o -name "*.conf" | tar -czvf
    ~/sm35_inputs.tgz -T -

    This program takes a subset of the ShakeMap 3.5 input data and the
    info.json file and uses those files to create the corresponding ShakeMap 4
    input data.

    Files used:
      - *_dat.xml data files in XML format. These are unchanged in
        ShakeMap 4.0.
      - *_fault.txt fault files in text format. These will be converted
        to GeoJSON.
      - source.txt Text file possibly containing mechanism and ??
      - info.json Metadata file from which we extract:
        - Origin information for new event.xml file.
        - bias settings (see -s option)
      - *.conf Config files, at this time only configs from grind.conf:
               - IPEs are currently not supported.
               - A partial subset of GMICE are supported in ShakeMap 4.0 at
                 this time.
               - GMPE selections will be converted to the closest matching
                 GEM equivalent (see -m).
               - outlier max_deviation and max_mag values will be converted.

    NOTE: if the -b option is used without -s, ShakeMap 4 will create a
    model.conf file for the event that does not specify a GMPE. To use a GMPE
    other than the default when running the event, make sure you update each
    event's model.conf file to include your chosen GMPE.

    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("tarfile", help="Input root data tarfile")
    hlptxt = """Ignore directories where event_source (from model.conf)
does not prepend eventid"""
    parser.add_argument(
        "-i", "--ignore-naked-ids", action="store_true", default=False, help=hlptxt
    )
    hlptxt2 = """Ignore previous bounds/resolution settings discovered
in input data."""
    hlptxt3 = """Ignore previous ground motion conversion settings discovered
in input data."""
    hlptxt4 = """Ignore new improved GMPE sets and attempt to use old GMPE
settings.  Note that this may result in errors when running ShakeMap. Not
recommended.
"""
    parser.add_argument(
        "-b", "--skip-bounds", action="store_true", default=False, help=hlptxt2
    )
    parser.add_argument(
        "-s", "--skip-settings", action="store_true", default=False, help=hlptxt3
    )
    parser.add_argument(
        "-u", "--use-old-gmpe", action="store_true", default=False, help=hlptxt4
    )
    parser.add_argument("-m", "--migrate-file", help="Supply custom migrate.conf")
    return parser


def _extract_file(member, tarball, filename, event_dir):
    datafile_object = tarball.extractfile(member)
    try:
        data = datafile_object.read().decode("utf-8")
    except Exception as e:
        raise e
    datafile_object.close()
    datafile = os.path.join(event_dir, filename)
    with open(datafile, "wt") as dfile:
        dfile.write(data)


def main():
    parser = get_parser()
    args, unknown = parser.parse_known_args()
    logger = logging.getLogger()
    logger.setLevel(logging.CRITICAL)
    install_path, data_path = get_config_paths()
    if not os.path.isdir(data_path):
        print(f"{data_path} is not a valid directory.")
        sys.exit(1)

    # get the system model.conf
    modelfile = os.path.join(install_path, "config", "model.conf")
    model_config = ConfigObj(modelfile)
    netid = model_config["system"]["source_network"]

    # load the migrate.conf file specified by user, if any
    if args.migrate_file:
        spec_file = get_configspec("migrate")
        validator = get_custom_validator()
        migrate_conf = ConfigObj(args.migrate_file, configspec=spec_file)
        results = migrate_conf.validate(validator)
        if not isinstance(results, bool) or not results:
            config_error(migrate_conf, results)
    else:
        migrate_conf = None

    # get the system modules.conf file, which tells us about implemented
    # GMICE
    modulefile = os.path.join(install_path, "config", "modules.conf")
    module_conf = ConfigObj(modulefile)

    # We're going to be inserting these events in the database later
    # handler = AmplitudeHandler(install_path, data_path)

    event_ids = []
    networks = {}

    # accumulate a list of errors so we can print them all at the end.
    errors = []
    conversions = {}
    print("Processing events...")

    # loop over events in the input tarball
    tarball = tarfile.open(args.tarfile, mode="r:gz")

    for member in tarball.getnames():
        # .getnames() returns all files in the tarball.

        if "save" in member:
            continue

        if tarball.getmember(member).isdir():
            continue

        parts = member.split("/")
        if parts[0] == ".":
            event_id = parts[1]
        else:
            event_id = parts[0]
        filename = parts[-1]

        if not event_id.startswith(netid):
            if args.ignore_naked_ids:
                # print('Skipping naked ID %s.' % event_id)
                continue
            else:
                event_id = netid + event_id

        if event_id not in event_ids:
            # print('Processing event %s...' % event_id)
            sys.stdout.write(".")
            sys.stdout.flush()
            event_ids.append(event_id)

        event_dir = os.path.join(data_path, event_id, "current")
        if not os.path.isdir(event_dir):
            event_dir = create_event_directory(event_id, data_path)

        # if these tarballs are made on a Mac, they may have done what
        # is described here:
        # https://superuser.com/a/61188
        # skip these files!
        if filename.startswith("._"):
            continue

        if filename.endswith(".conf"):
            cfg_errors, tconversions = parse_config(
                event_dir, tarball, member, migrate_conf=migrate_conf
            )
            errors += cfg_errors
            conversions.update(tconversions)
        elif filename.endswith("_dat.xml"):
            _extract_file(member, tarball, filename, event_dir)
        elif filename.endswith("_fault.txt"):
            _extract_file(member, tarball, filename, event_dir)
        elif filename.startswith("RUN"):
            run_errors = parse_run(member, tarball, filename, event_dir)
            errors += run_errors
        elif filename in ["info.json"]:
            if "download" in member:
                continue
            edict, info_errors, info_conversions = parse_info(
                event_dir,
                tarball,
                member,
                netid,
                networks,
                module_conf,
                skip_bounds=args.skip_bounds,
                skip_settings=args.skip_settings,
                use_old_gmpe=args.use_old_gmpe,
            )
            errors += info_errors
            conversions.update(info_conversions)
            # handler.insertEvent(edict)
        elif filename == "source.txt":
            _extract_file(member, tarball, filename, event_dir)
        else:
            errors.append(f"Unknown input file {filename} for event {event_id}")

    tarball.close()
    sys.stdout.write("\n")

    # go back through the data, convert fault.txt files into json rupture
    # format, also make sure we have all required components
    print("Converting *_fault.txt files to geojson files...")
    for event_id in event_ids:
        print(f"    {event_id}")
        event_dir = os.path.join(data_path, event_id, "current")
        rupt_error = make_rupture(event_dir)
        parse_options(event_dir)
        if rupt_error is not None:
            errors.append(rupt_error)

    print("%i event directories written." % len(event_ids))
    print("The following errors or warnings were detected:")
    for error in errors:
        print(f'\t"{error}"')

    print("The following GMPE conversions were applied:")
    for old_gmpe, gmpe_tuple in conversions.items():
        new_gmpe, ref = gmpe_tuple
        print(f'\t"{old_gmpe}" ({ref}) was converted to new GMPE "{new_gmpe}".')


def parse_options(event_dir):
    optfile = os.path.join(event_dir, "options.json")
    if not os.path.isfile(optfile):
        return
    eventfile = os.path.join(event_dir, "event.xml")
    edict = read_event_file(eventfile)
    options = json.load(open(optfile, "rt"))
    model = ConfigObj(indent_type="    ")
    if "nobias" in options:
        model["modeling"] = {"bias": {"do_bias": False}}
    if "nooutlier" in options:
        model["data"] = {"outlier": {"do_outlier": False}}
    bounds_options = set(["latoff", "lonoff", "lonspan", "llratio"])
    opt_keys = set(options.keys())
    if len(bounds_options.intersection(opt_keys)):
        lat = edict["lat"]
        lon = edict["lon"]
        if "lonoff" in options:
            lon = lon + options["lonoff"]
        if "latoff" in options:
            lat = lat + options["latoff"]
        if "lonspan" in options:
            xmin = lon - options["lonspan"] / 2.0
            xmax = lon + options["lonspan"] / 2.0
            if "llratio" in options:
                latspan = options["llratio"] * options["lonspan"]
            else:
                latspan = options["lonspan"] * np.cos(np.degrees(lat))
            ymin = lat - latspan / 2.0
            ymax = lat + latspan / 2.0
        else:
            # create a rupture
            edict["lat"] = lat
            edict["lon"] = lon
            # use get_rupture function?
            origin = Origin(edict)
            rfile = os.path.join(event_dir, "rupture.json")
            if not os.path.isfile(rfile):
                rfile = None
            rupture = get_rupture(origin, file=rfile)
            xmin, xmax, ymin, ymax = get_extent(rupture)
        model["extent"] = {"bounds": {}}
        model["extent"]["bounds"]["extent"] = [xmin, ymin, xmax, ymax]
        if len(model):
            model_file = os.path.join(event_dir, "model.conf")
            if os.path.isfile(model_file):
                existing_model = ConfigObj(model_file, indent_type="    ")
                model.merge(existing_model)
        model.filename = model_file
        model.write()


def parse_run(member, tarball, filename, event_dir):
    errors = []
    options = {}
    float_options = ["lonspan", "latspan", "lonoff", "latoff", "llratio"]
    bool_options = ["nooutlier", "nobias"]
    for line in open(filename, "rt").readlines():
        if line.find("grind") > -1:
            parts = line.split()[1:]
            for i in range(0, len(parts)):
                part = parts[i].strip()
                isfloat = re.search(r"[+-]?\d+(?:\.\d+)?", part) is not None
                if part.startswith("-") and not isfloat:
                    part = part.replace("-", "")
                    if part == "-directivity":
                        fmt = "Unsupported directivity flag set for " "event %s."
                        errors.append(fmt % event_dir)
                    elif part in float_options:
                        options[part] = float(parts[i + 1])
                    elif part in bool_options:
                        options[part] = True
                    else:
                        continue
    # Since we don't know hypocenter information at this stage, we're going to
    # stash this dictionary in the event directory as JSON and parse it at
    # the end.
    optionfile = os.path.join(event_dir, "options.json")
    with open(optionfile, "wt") as opt:
        json.dump(options, opt)

    return errors


def make_rupture(event_dir):
    fault_files = glob.glob(os.path.join(event_dir, "*_fault.txt"))
    if not len(fault_files):
        return
    fault_file = fault_files[0]
    xmlfile = os.path.join(event_dir, "event.xml")
    eqdict = read_event_file(xmlfile)
    try:
        jdict = text_to_json(fault_file, new_format=False)
        origin = Origin(eqdict)
        rupt = rupture_from_dict_and_origin(jdict, origin)
    except Exception as e:
        return f'Error parsing fault file from {event_dir}. "{str(e)}"'
    jsonfile = os.path.join(event_dir, "rupture.json")
    rupt.writeGeoJson(jsonfile)
    for ffile in fault_files:
        os.remove(ffile)


def parse_config(event_dir, tarball, member, migrate_conf=None):
    errors = []
    conversions = {}
    if "shake.conf" in member:
        pass
    elif "grind_zc2.conf" in member:
        pass
    elif "grind.conf" in member:
        pass
    elif "db.conf" in member:
        pass
    elif "timezone.conf":
        pass
    elif "retrieve.conf" in member:
        pass
    else:
        errors.append(f"Unknown config file type {member}")

    return (errors, conversions)


def parse_info(
    event_dir,
    tarball,
    member,
    netid,
    networks,
    module_conf,
    skip_bounds=False,
    skip_settings=False,
    migrate_conf=None,
    use_old_gmpe=False,
):
    install_path, data_path = get_config_paths()
    config = ConfigObj(os.path.join(install_path, "config", "select.conf"))
    global_data_path = os.path.join(os.path.expanduser("~"), "shakemap_data")
    validate_config(config, install_path, data_path, global_data_path)

    jsonfile = tarball.extractfile(member)
    jsonstring = jsonfile.read().decode("utf-8")
    jsondict = json.loads(jsonstring)

    # accumulate error messages
    errors = []

    # accumulate gmpe conversions
    conversions = {}

    # get the origin information out of the json
    xmlfile = os.path.join(event_dir, "event.xml")
    edict = {}
    edict["id"] = jsondict["input"]["event_information"]["event_id"]
    timestring = jsondict["input"]["event_information"]["origin_time"]
    edict["time"] = HistoricTime.strptime(timestring, constants.ALT_TIMEFMT)
    edict["netid"] = netid
    if netid in networks:
        edict["network"] = networks[netid]
    else:
        network = get_network_name(netid)
        if network == "unknown":
            network = ""
        networks[netid] = network
        edict["network"] = network
    edict["lat"] = jsondict["input"]["event_information"]["latitude"]
    edict["lon"] = jsondict["input"]["event_information"]["longitude"]
    edict["depth"] = jsondict["input"]["event_information"]["depth"]
    edict["mag"] = jsondict["input"]["event_information"]["magnitude"]
    edict["locstring"] = jsondict["input"]["event_information"]["location"]
    edict["mech"] = jsondict["input"]["event_information"]["src_mech"]
    write_event_file(edict, xmlfile)

    # get the above info as an amps.db event dictionary
    eqdict = {
        "id": edict["id"],
        "netid": edict["netid"],
        "network": edict["network"],
        "time": timestring[0:19] + ".000Z",
        "lat": edict["lat"],
        "lon": edict["lon"],
        "depth": edict["depth"],
        "mag": edict["mag"],
        "locstring": edict["locstring"],
    }

    model = ConfigObj(indent_type="    ")
    if not skip_settings:
        # get all of the bias information
        model["modeling"] = {"bias": {}}
        bias_max_mag = jsondict["processing"]["miscellaneous"]["bias_max_mag"]
        max_range = jsondict["processing"]["miscellaneous"]["bias_max_range"]
        if bias_max_mag > 0 and max_range > 0:
            model["modeling"]["bias"]["do_bias"] = True
            model["modeling"]["bias"]["max_range"] = max_range
            model["modeling"]["bias"]["max_mag"] = bias_max_mag
        else:
            model["modeling"]["bias"]["do_bias"] = False

        # get the outlier information
        model["data"] = {"outlier": {}}
        jpm = jsondict["processing"]["miscellaneous"]
        max_deviation = jpm["outlier_deviation_level"]
        outlier_max_mag = jpm["outlier_max_mag"]
        if outlier_max_mag > 0 and max_deviation > 0:
            model["data"]["outlier"]["do_outlier"] = True
            model["data"]["outlier"]["max_deviation"] = max_deviation
            model["data"]["outlier"]["max_mag"] = outlier_max_mag
        else:
            model["data"]["outlier"]["do_outlier"] = False

        # get the gmice information
        allowed_gmice = module_conf["gmice_modules"].keys()
        jpg = jsondict["processing"]["ground_motion_modules"]
        gmice = jpg["mi2pgm"]["module"]
        # WGRW11 in SM3.5 is WGRW12 in SM4.0
        if gmice == "WGRW11":
            gmice = "WGRW12"
        if gmice not in allowed_gmice:
            errors.append(
                f"GMICE {gmice} (event {edict['id']}) not yet supported in ShakeMap 4."
            )
        else:
            model["modeling"]["gmice"] = gmice

        if use_old_gmpe:
            # get the GMPE information
            gmm_dict = jsondict["processing"]["ground_motion_modules"]
            old_gmpe = gmm_dict["gmpe"]["module"]
            try:
                new_gmpe, reference = migrate_gmpe(old_gmpe, config=migrate_conf)
                model = set_gmpe(new_gmpe, model, edict["id"])
                if old_gmpe not in conversions:
                    conversions[old_gmpe] = (new_gmpe, reference)
            except Exception as e:
                msg = f'Unable to convert {old_gmpe}, error "{str(e)}"'
                errors.append(msg)
        else:
            org = Origin(eqdict)
            config = update_config_regions(org.lat, org.lon, config)
            gmm_dict, strec_results = get_weights(org, config)
            gmpe_set = "gmpe_" + eqdict["id"] + "_custom"
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
            model["modeling"]["gmpe"] = gmpe_set
            model["modeling"]["mechanism"] = strec_results["FocalMechanism"]
            if gmm_dict["ipe"]:
                model["modeling"]["ipe"] = gmm_dict["ipe"]
            if gmm_dict["gmice"]:
                model["modeling"]["gmice"] = gmm_dict["gmice"]
            if gmm_dict["ccf"]:
                model["modeling"]["ccf"] = gmm_dict["ccf"]

    # work on map extent/resolution data
    if not skip_bounds:
        model["interp"] = {"prediction_location": {}}
        jom = jsondict["output"]["map_information"]
        yres_km = jom["grid_spacing"]["latitude"]
        yres_sec = int(round(yres_km * KM2SEC))
        model["interp"]["prediction_location"]["xres"] = "%ic" % yres_sec
        model["interp"]["prediction_location"]["yres"] = "%ic" % yres_sec

        model["extent"] = {"bounds": {}}
        xmin = jsondict["output"]["map_information"]["min"]["longitude"]
        xmax = jsondict["output"]["map_information"]["max"]["longitude"]
        ymin = jsondict["output"]["map_information"]["min"]["latitude"]
        ymax = jsondict["output"]["map_information"]["max"]["latitude"]
        model["extent"]["bounds"]["extent"] = [xmin, ymin, xmax, ymax]

    # done with model.conf, merge with existing file and save
    if len(model):
        model_file = os.path.join(event_dir, "model.conf")
        if os.path.isfile(model_file):
            existing_model = ConfigObj(model_file, indent_type="    ")
            model.merge(existing_model)
        model.filename = model_file
        model.write()

    return (eqdict, errors, conversions)


def create_event_directory(event_id, data_path):
    event_dir = os.path.join(data_path, event_id, "current")
    if os.path.isdir(event_dir):
        return None
    os.makedirs(event_dir)
    return event_dir


if __name__ == "__main__":
    main()
