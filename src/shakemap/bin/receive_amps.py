#!/usr/bin/env python

# stdlib imports
import argparse
import os.path
import sys
import glob

# local imports
from shakemap_modules.utils.config import get_config_paths
from shakemap_modules.utils.amps import AmplitudeHandler
from shakemap_modules.utils.logging import get_generic_logger

LOGFILE = "amps.log"


def get_parser():
    """Set up the argparse instance for this script.

    Returns:
        ArgumentParser: argparse instance for this script.
    """
    description = """Insert strong motion unassociated peak amplitude
    files into a database.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--directory",
        help="Directory containing unassociated strong " "motion peak amplitudes",
    )

    return parser


def main():
    """Main method for script."""
    clean_argv = " ".join(
        [x.replace('"', "").replace("=", " ", 1) for x in sys.argv]
    ).split()
    parser = get_parser()
    args, unknown = parser.parse_known_args(clean_argv)
    install_path, data_path = get_config_paths()
    if not os.path.isdir(data_path):
        print(f"{data_path} is not a valid directory.")
        sys.exit(1)

    # set up a daily rotating file handler logger
    logfile = os.path.join(install_path, "logs", LOGFILE)
    logger = get_generic_logger(logfile=logfile)

    logger.info(f"Parsing input directory {args.directory}")

    # Create a handler object
    handler = AmplitudeHandler(install_path, data_path)

    logger.info(f"Searching {args.directory}...")
    xmlfiles = glob.glob(os.path.join(args.directory, "*.xml"))
    nloaded = 0
    for xmlfile in xmlfiles:
        if xmlfile.endswith("product.xml"):
            continue
        try:
            handler.insertAmps(xmlfile)
            nloaded += 1
        except Exception as e:
            logger.info(f'Could not insert file {xmlfile}: "{str(e)}"')
            # TODO - configure a directory where "bad" amps files can go
            continue
    logger.info("Inserted %i amplitude files into the database." % nloaded)


if __name__ == "__main__":
    main()
