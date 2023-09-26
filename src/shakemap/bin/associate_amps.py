#!/usr/bin/env python

# stdlib imports
import argparse
import os.path
import sys

# local imports
from shakemap_modules.utils.config import get_config_paths
from shakemap_modules.utils.amps import AmplitudeHandler
from shakemap_modules.utils.logging import get_generic_logger

LOGFILE = "associate.log"


def get_parser():
    description = """Associate any un-associated amplitudes with existing
    ShakeMap events.

    Amplitude data will be written to event data directories in ShakeMap
    station XML format.
    """
    parser = argparse.ArgumentParser(description=description)
    return parser


def main():
    parser = get_parser()
    args, unknown = parser.parse_known_args()
    install_path, data_path = get_config_paths()
    if not os.path.isdir(data_path):
        print(f"{data_path} is not a valid directory.")
        sys.exit(1)

    # set up a daily rotating file handler logger
    logfile = os.path.join(install_path, "logs", LOGFILE)
    logger = get_generic_logger(logfile=logfile)

    # what to do if the database is locked by another process?
    handler = AmplitudeHandler(install_path, data_path)

    # scan the event table and find any data that is associated with each event

    logger.info("Searching for amp data to associate.")
    associated = handler.associateAll(pretty_print=True)
    logger.info("Found amplitude data for %i events." % (len(associated)))


if __name__ == "__main__":
    main()
