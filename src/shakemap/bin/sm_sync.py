#!/usr/bin/env python

# stdlib imports
import argparse
import os.path
import shutil
import sys
from configparser import ConfigParser

# third party imports

# local imports
from esi_utils_io.cmd import get_command_output
from shakemap_modules.utils.config import get_config_paths

CONFIG = "sync.conf"
EXCLUDES = ["backup*", "pdl", "products", "*.hdf"]


def main():
    help = """Synchronize data from local system with ShakeMap servers.

This program assumes that you have a configuration file located in ~/.shakemap/sync.conf.
This file will look something like this:

#################################################
[servers]
  primary = server1

[server1]
  user = shake
  server = myserver1.org
  datadir = /data/shake
  installdir = /home/shake/profiles/shake_prof/install/

[server2]
  user = shake
  server = myserver2.org
  datadir = /data/shake
  installdir = /home/shake/profiles/shake_prof/install/
#################################################

"""
    parser = argparse.ArgumentParser(
        description=help, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    optgroup = parser.add_mutually_exclusive_group()
    parser.add_argument("eventid", metavar="EVENTID", help="Event ID to synchronize.")
    optgroup.add_argument(
        "--pull",
        action="store_true",
        default=False,
        help="Pull data from remote server",
    )
    optgroup.add_argument(
        "--push",
        action="store_true",
        default=False,
        help="Push modified data to remote server.",
    )
    optgroup.add_argument(
        "-l",
        "--list",
        action="store_true",
        default=False,
        help="List available servers.",
    )
    parser.add_argument(
        "-s", "--server", help="Choose alternate server to synchronize with."
    )

    args = parser.parse_args()
    # is rsync available on this system?
    cmd = shutil.which("rsync")
    if cmd is None:
        print("The rsync utility is not available on this system.")
        sys.exit(1)

    if not args.pull and not args.push and not args.list:
        print("\nYou must specify one of --pull, --push, or --list.")
        parser.print_help()
        sys.exit(0)

    configdir = os.path.join(os.path.expanduser("~"), ".shakemap")
    syncfile = os.path.join(configdir, CONFIG)
    if not os.path.isfile(syncfile):
        fmt = "You do not have a synchronization config file at %s. Exiting."
        print(fmt % syncfile)
        sys.exit(1)

    install_path, data_path = get_config_paths()
    config = ConfigParser()
    config.read(syncfile)

    # is the servers section present?
    if "servers" not in config.sections():
        print("You must have a [servers] section configured.")
        sys.exit(1)

    servers = config.sections()
    servers.remove("servers")
    if args.list:
        print("Servers:")
        for server in servers:
            print(f"  {server}:")
            for key, value in config[server].items():
                print(f"    {key} = {value}")
        sys.exit(0)

    server = config["servers"]["primary"]
    if args.server:
        server = args.server
    if server not in servers:
        print(f"Server {server} is not configured.")
        sys.exit(1)

    hostname = config[server]["server"]
    user = config[server]["user"]
    tremote_dir = config[server]["datadir"]

    remote_dir = os.path.join(tremote_dir, args.eventid) + os.path.sep
    local_dir = os.path.join(data_path, args.eventid) + os.path.sep

    excludes = [f"--exclude={exclude}" for exclude in EXCLUDES]
    excludestr = " ".join(excludes)

    if args.pull:
        source = f"{user}@{hostname}:{remote_dir}"
        dest = local_dir
        options = "-auzr"
        msg = "Retrieving data from server..."

    if args.push:
        if not os.path.isdir(local_dir):
            print(f"You do not have event {args.eventid} on this system. Exiting.")
            sys.exit(1)
        source = local_dir
        dest = f"{user}@{hostname}:{remote_dir}"
        options = "-tauzr"
        msg = "Syncing data to server..."

    command = f"{cmd} {options} {excludestr} {source} {dest}"
    print(command)
    print(msg)
    res, stdout, stderr = get_command_output(command)
    if not res:
        print(f"rsync command {command} failed.\n{stderr}\n{stdout}.")
        sys.exit(1)
    else:
        if args.pull:
            print(f"Data synchronized successfully to local path {local_dir}")
        else:
            print(f"Data synchronized successfully to remote path {remote_dir}")

    sys.exit(0)


if __name__ == "__main__":
    main()
