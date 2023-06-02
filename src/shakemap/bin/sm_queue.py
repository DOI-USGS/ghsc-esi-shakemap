#! /usr/bin/env python

# System imports
import argparse

# Third-party imports

# Local imports
from shakemap.utils.queue import Queue


def get_parser():
    """Make an argument parser.

    Returns:
        ArgumentParser: an argparse argument parser.
    """
    description = """
    Run a daemon process to accept origin, rupture, fault, etc., messages
    and run shake on the event.
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-a",
        "--attached",
        action="store_true",
        help="Inhibit daemonization and remain attached " "to the terminal.",
    )
    parser.add_argument(
        "-b",
        "--break_lock",
        action="store_true",
        help="If the pid lock file can't be acquired, break "
        "the existing lock and acquire a new lock. Do "
        "this only if you are certain tha no other "
        "sm_queue processes are running.",
    )
    return parser


def main():
    parser = get_parser()
    pargs = parser.parse_args()

    sm_queue = Queue(pargs)
    sm_queue.queueMainLoop()


if __name__ == "__main__":
    main()
