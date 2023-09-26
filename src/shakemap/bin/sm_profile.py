#!/usr/bin/env python
"""
Manage ShakeMap profiles. Profiles allow the user to maintain multiple
ShakeMap configurations and data directories. sm_profile allows the
user to create, delete, and switch between profiles.
Files:
    ~/.shakemap/profiles.conf
"""

# stdlib imports
import os
import argparse
from configobj import ConfigObj
import os.path
import sys
import shutil
import pathlib
import glob
import textwrap
import urllib.request
from tempfile import mkstemp
import re

# shakemap imports
from shakemap_modules.utils.config import get_data_path
from shakemap_modules.utils.config import check_profile_config
from shakemap_modules.utils.utils import query_yes_no


def replace(file_path, pattern, subst):
    """Function I found on stackoverflow to replace a pattern in a file"""
    # Create temp file
    fh, abs_path = mkstemp()
    with os.fdopen(fh, mode="w", encoding="utf-8-sig") as new_file:
        with open(file_path, mode="r", encoding="utf-8-sig") as old_file:
            for line in old_file:
                new_file.write(re.sub(pattern, subst, line))
    # Remove original file
    os.remove(file_path)
    # Move new file
    shutil.move(abs_path, file_path)


def get_parser():
    desc = """ Manage ShakeMap profiles.
These ShakeMap profiles allow one user to have multiple ShakeMap profiles
(installations) on the same machine.  These profiles can all be configured
differently, if desired. By default the profiles reside in the file
'~/.shakemap/profiles.conf'.
"""
    parser = argparse.ArgumentParser(description=desc, epilog="\n\n")
    parser.add_argument(
        "-s",
        "--switch",
        metavar="PROFILE",
        help="Switch from current profile to PROFILE.",
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="List all configured profiles."
    )
    parser.add_argument(
        "-c",
        "--create",
        metavar="PROFILE",
        help="Create new profile PROFILE and switch to it.",
    )
    parser.add_argument(
        "-d", "--delete", metavar="PROFILE", help="Delete existing profile PROFILE."
    )
    parser.add_argument(
        "-a",
        "--accept",
        action="store_true",
        help="Accept the defaults when creating or " "deleting a profile.",
    )
    parser.add_argument(
        "-n",
        "--nogrids",
        action="store_true",
        help="Do not attempt to download the topo or vs30 " "grids.",
    )
    parser.add_argument(
        "-p",
        "--preserve",
        action="store_true",
        help="Preserve data when deleting a profile",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=str,
        help="Specify an alternative file in which the " "profiles (will) reside",
    )
    return parser


current_markers = {True: "**Current Profile**", False: ""}


class ShakeProfile(object):
    def __init__(self, name, indict, is_current=False):
        self.name = name
        self.install_path = indict["install_path"]
        self.data_path = indict["data_path"]
        self.current_marker = current_markers[is_current]

    def __repr__(self):
        fmt = "Profile: %s %s\n\tInstall Path: %s\n\tData Path: %s"
        tpl = (self.name, self.current_marker, self.install_path, self.data_path)
        return fmt % tpl


def make_dir(pathstr, default, accept):
    max_tries = 3
    ntries = 1
    make_ok = False
    ppath = ""
    while not make_ok:
        if not accept:
            ppath = input(f"Please enter the {pathstr}: [{default}] ")
        else:
            ppath = default
        if not len(ppath.strip()):
            ppath = default
        try:
            os.makedirs(ppath, exist_ok=True)
            make_ok = True
        except OSError:
            msg = (
                "Cannot make install_folder %s.  Please try again (%d " "of %d tries)."
            )
            print("\n".join(textwrap.wrap(msg % (ppath, ntries, max_tries))))
            ntries += 1
        if ntries > max_tries:
            break
    return (ppath, make_ok)


def create(config, profile, accept, ppath, nogrids):
    """
    Args:
        config (ConfigObj): ConfigObj instance representing the
            parsed config.
        profile (str): Profile name.
        accept (bool): Should defaults be accepted?
        ppath (str): Path to an alternative profile location (optional).
        nogrids (bool): If true, will skip the step of downloading topo
            and Vs30 grids.
    """
    shakeconfig_data_path = get_data_path()

    if ppath:
        profile_path = os.path.join(ppath, profile)
    else:
        profile_path = os.path.join(
            os.path.expanduser("~"), "shakemap_profiles", profile
        )
    default_install = os.path.join(profile_path, "install")
    default_data = os.path.join(profile_path, "data")
    if not accept:
        print(
            "\n".join(
                textwrap.wrap(
                    "You will be prompted to supply two directories for this "
                    "ShakeMap profile:"
                )
            )
        )
        print(
            "\n   ".join(
                textwrap.wrap(
                    " - An *installation* path, under which will be created "
                    "directories for system configuration, (config), logging "
                    "(logs), and support data (data)."
                )
            )
        )
        print(
            "\n   ".join(
                textwrap.wrap(
                    " - A *data* path, under which will be created directories for "
                    "each event processed.\n"
                )
            )
        )

    install_path, install_ok = make_dir("install path", default_install, accept)
    if not install_ok:
        print(
            "\n".join(
                textwrap.wrap(
                    "Please try to find a path that can be created on this "
                    "system and then try again.  Exiting."
                )
            )
        )
        sys.exit(1)
    new_data_path, data_ok = make_dir("data path", default_data, accept)
    if not data_ok:
        print(
            "\n".join(
                textwrap.wrap(
                    "Please try to find a path that can be created on this "
                    "system and then try again.  Exiting."
                )
            )
        )
        shutil.rmtree(install_path)
        sys.exit(1)

    # put the default config files in the install path
    config_path = os.path.join(install_path, "config")
    if not os.path.isdir(config_path):
        os.mkdir(config_path)

    # create a directory where global log files will be written
    log_path = os.path.join(install_path, "logs")
    if not os.path.isdir(log_path):
        os.mkdir(log_path)

    # set up all of the config files
    conf_names = [
        "modules.conf",
        "gmpe_sets.conf",
        "model.conf",
        "select.conf",
        "products.conf",
        "shake.conf",
        "logging.conf",
        "transfer.conf",
        "migrate.conf",
    ]

    # if any of these files are not present in the install config
    # directory, copy them from the repository into the install directory.
    for conf_name in conf_names:
        config_file = shakeconfig_data_path / conf_name
        if not os.path.isfile(os.path.join(config_path, conf_name)):
            shutil.copy(config_file, config_path)

    layer_dir = shakeconfig_data_path / "layers"
    install_data_dir = os.path.join(install_path, "data")
    mapping_data_dir = os.path.join(install_data_dir, "mapping")
    generic_amps_dir = os.path.join(install_data_dir, "GenericAmpFactors")
    install_layer_dir = os.path.join(install_data_dir, "layers")

    if not os.path.isdir(install_layer_dir):
        shutil.copytree(layer_dir, install_layer_dir)

    if not os.path.isdir(install_data_dir):
        os.mkdir(install_data_dir)

    if not os.path.isdir(generic_amps_dir):
        os.mkdir(generic_amps_dir)

    if not os.path.isdir(mapping_data_dir):
        os.mkdir(mapping_data_dir)

    # copy mapping data into data install directory
    test_mapping_dir = (
        shakeconfig_data_path
        / ".."
        / ".."
        / "tests"
        / "data"
        / "install"
        / "data"
        / "mapping"
    )
    allfiles = glob.glob(os.path.join(test_mapping_dir, "*.*"))
    for fname in allfiles:
        shutil.copy(fname, mapping_data_dir)

    if "profiles" not in config:
        config["profiles"] = {}
    config["profiles"][profile] = {
        "install_path": install_path,
        "data_path": new_data_path,
    }
    #    config.filename = configfile
    config["profile"] = profile
    config.write()
    sprofile = ShakeProfile(profile, config["profiles"][profile])
    print(f"\nCreated profile: {sprofile}")

    if nogrids:
        return

    do_vs30 = True
    if not accept:
        do_vs30 = query_yes_no(
            "Do you want to download the global " "topography and Vs30 files?"
        )
        if do_vs30:
            print(
                "\n".join(
                    textwrap.wrap(
                        "You will be prompted for a path where the topo and Vs30 data "
                        "will reside."
                    )
                )
            )

    if do_vs30 is False:
        return

    gdata_default = os.path.join(os.path.expanduser("~"), "shakemap_data")
    gdata_path, install_ok = make_dir("data path", gdata_default, accept)
    if not install_ok:
        print(
            "\n".join(
                textwrap.wrap(
                    "Please try to find a path that can be created on this "
                    "system and then try again.  Exiting."
                )
            )
        )
        sys.exit(1)
    topo_path = os.path.join(gdata_path, "topo")
    if not os.path.isdir(topo_path):
        os.mkdir(topo_path)
    vs30_path = os.path.join(gdata_path, "vs30")
    if not os.path.isdir(vs30_path):
        os.mkdir(vs30_path)
    #
    # url info
    #
    url_machine = "https://apps.usgs.gov/"
    url_topo_dir = "shakemap_geodata/topo/"
    url_vs30_dir = "shakemap_geodata/vs30/"
    topo_file = "topo_30sec.grd"
    vs30_file = "global_vs30.grd"

    print("Retrieving global topo and Vs30 files. This may take a minute...")
    url = url_machine + url_topo_dir + topo_file
    topo_file_path = os.path.join(topo_path, topo_file)
    with urllib.request.urlopen(url) as response, open(
        topo_file_path, "wb"
    ) as out_file:
        shutil.copyfileobj(response, out_file)
    url = url_machine + url_vs30_dir + vs30_file
    vs30_file_path = os.path.join(vs30_path, vs30_file)
    with urllib.request.urlopen(url) as response, open(
        vs30_file_path, "wb"
    ) as out_file:
        shutil.copyfileobj(response, out_file)
    print("Done.")

    do_config = True
    if not accept:
        do_config = query_yes_no(
            "Do you want to configure your system to use these files?"
        )
    if do_config is False:
        return

    print("Configuring profile to use downloaded topo and vs30 files...")

    my_config = os.path.join(config_path, "products.conf")
    old_line = r"topography\s*=\s*.*"
    new_line = f"topography = {topo_file_path}"
    replace(my_config, old_line, new_line)

    my_config = os.path.join(config_path, "model.conf")
    old_line = r"vs30file\s*=\s*.*"
    new_line = f"vs30file = {vs30_file_path}"
    replace(my_config, old_line, new_line)

    print("Done.")


def main():
    """ """
    parser = get_parser()
    args = parser.parse_args()
    if args.file:
        configfile = args.file
        ppath = os.path.dirname(configfile)
    else:
        configdir = os.path.join(os.path.expanduser("~"), ".shakemap")
        if not os.path.isdir(configdir):
            pathlib.Path(configdir).mkdir(exist_ok=True)
        configfile = os.path.join(configdir, "profiles.conf")
        ppath = ""
    if not os.path.isfile(configfile):
        pathlib.Path(configfile).touch(exist_ok=True)

    config = ConfigObj(configfile, encoding="utf-8-sig")

    if args.create:
        profile = args.create
        if "profiles" in config and profile in config["profiles"]:
            msg = "Profile %s already in %s.  Run %s -l to see available " "profiles."
            print(msg % (profile, configfile, parser.prog))
            sys.exit(1)
        create(config, profile, args.accept, ppath, args.nogrids)
        sys.exit(0)

    config = check_profile_config(config)

    if args.list:
        profiles = config["profiles"]
        current = config["profile"]
        for profname, profdict in profiles.items():
            is_current = False
            if profname == current:
                is_current = True
            sprofile = ShakeProfile(profname, profdict, is_current=is_current)
            print("\n" + str(sprofile) + "\n")
        sys.exit(0)

    if args.switch:
        newprofile = args.switch
        if newprofile not in config["profiles"]:
            msg = "Profile %s not in %s.  Run %s -l to see " "available profiles."
            print(msg % (newprofile, configfile, parser.prog))
            sys.exit(1)
        config["profile"] = newprofile
        config.filename = configfile
        config.write()
        sp = ShakeProfile(newprofile, config["profiles"][newprofile], is_current=True)
        print(f"\nSwitched to profile: \n{str(sp)}\n")
        sys.exit(0)

    if args.delete:
        profile = args.delete
        if profile not in config["profiles"]:
            msg = "Profile %s not in %s.  Run %s -l to available profiles."
            print(msg % (profile, configfile, parser.prog))
            sys.exit(1)

        install_path = config["profiles"][profile]["install_path"]
        data_path = config["profiles"][profile]["data_path"]
        if not args.preserve:
            question = (
                "Are you sure you want to delete everything in:\n"
                "%s\n--and--\n%s?\n" % (install_path, data_path)
            )
            if not args.accept and not query_yes_no(question, default="yes"):
                sys.exit(0)
            shutil.rmtree(install_path, ignore_errors=True)
            shutil.rmtree(data_path, ignore_errors=True)

        del config["profiles"][profile]

        if config["profiles"].keys() == []:
            print("No remaining profiles in profiles.conf")
            default = None
            newprofile = "None"
        else:
            default = config["profiles"].keys()[0]
            newprofile = ShakeProfile(default, config["profiles"][default])
        config["profile"] = default

        config.filename = configfile
        config.write()
        print(f"Deleted profile {profile}:")
        print(f"\tDeleted install directory {install_path}:")
        print(f"\tDeleted data directory {data_path}:")

        print("\nSet to new profile:\n")
        print(newprofile)
        sys.exit(0)

    if args.accept:
        print("The -a argument must be used in conjunction with -c.")
        sys.exit(1)

    profile = config["profile"]
    profiles = config["profiles"]
    if profile not in profiles:
        msg = (
            "Current profile %s not in %s. Edit your profiles.conf "
            "file to match the specification."
        )
        print(msg % (profile, configfile))
        sys.exit(1)
    sprofile = ShakeProfile(profile, profiles[profile], is_current=True)
    print(sprofile)
    sys.exit(0)


if __name__ == "__main__":
    main()
