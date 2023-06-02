#!/usr/bin/env python

# stdlib imports
import argparse
import glob
import os.path
import shutil
import sys

import numpy as np

# third party imports
from esi_utils_io.cmd import get_command_output

CONFIG_DIR = ".shakemap"
CONFIG_FILE = "profiles.conf"

SHAKE_COMMAND = "shake"


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass


def call_shakemap(cmd, events, modules, logfile):
    """Loop over a list of event IDs, calling ShakeMap on each one.

    Args:
        cmd (str):
            Path to shake command.
        events (list):
            List of event IDs which correspond to event directories under current
            profile.
        modules (list):
            List of ShakeMap modules to run.
        logfile (file):
            Open file object where child process can write output.
    Returns:
        tuple: (Boolean indicating success/failure, stdout from shake call, stderr from
        shake call)
    """
    modstr = " ".join(modules)
    for event in events:
        cmdstr = f"{cmd} {event} {modstr}"
        res, stdout, stderr = get_command_output(cmdstr)
        if not res:
            logfile.write(f'Failure for event {event}: "{stdout + stderr}"\n')
    return (res, stdout, stderr)


def main():
    description = """ShakeMap batch process from a list of event IDs.

-n option should be chosen intelligently to be lower than the number of
cores present on the system.

-m modules should be specified in the correct order (select should precede assemble, etc.)

-c Comment string should perhaps indicate the reason why batch run is happening.
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=CustomFormatter
    )
    parser.add_argument("file", help="Text file with one ID per line.")

    nphlp = (
        "Number of instances of ShakeMap that should "
        "be run simultaneously. "
        "The value given to -n should generally be less than "
        "or equal to the number of cores on the machine."
    )
    parser.add_argument("-n", "--num-processes", help=nphlp, default=4, type=int)

    mhelp = "List of ShakeMap modules to run on each event. "
    parser.add_argument("-m", "--modules", nargs="+", default=[], help=mhelp)

    parser.add_argument(
        "-c", "--comment", default="testing", help="Comment for assemble module"
    )

    args = parser.parse_args()
    # check for the existence of the shake program
    shake = shutil.which(SHAKE_COMMAND)
    if shake is None:
        print('Could not find "shake" on your path. Exiting.')
        sys.exit(1)

    new_modules = []
    comment = args.comment
    for module in args.modules:
        if module == "assemble":
            modstr = f'assemble -c "{comment}"'
        else:
            modstr = module
        new_modules.append(modstr)

    # now break up the input file into N chunks to process
    # read all the event ids
    events = open(args.file, "rt").readlines()
    # remove trailing newline from each event
    events = [event.strip() for event in events]

    # peel off the first event, call shake and see if it works
    # if not, exit with some kind of useful error
    test_event = events.pop(0)
    print(f"Testing input with the event {test_event}...")
    logfile = "test_log.log"
    f = open(logfile, "wt")
    res, stdout, stderr = call_shakemap(shake, [test_event], new_modules, f)
    f.close()
    os.remove(logfile)
    if not res:
        print(f'The test event failed with output: "{stdout}" "{stderr}"')
        sys.exit(1)
    else:
        print("Test event succeeded. Parallelization commencing...")

    chunks = np.array_split(events, args.num_processes)
    homedir = os.path.expanduser("~")
    logbase = "shake_batch_log_"
    logfmt = logbase + "%i.txt"

    # now run each chunk in parallel. ??
    for i in range(0, len(chunks)):
        try:
            pid = os.fork()
        except OSError:
            sys.stderr.write("Could not create a child process\n")
            continue

        if pid == 0:
            chunk = chunks[i]
            logfile = os.path.join(homedir, logfmt % os.getpid())
            f = open(logfile, "wt")
            call_shakemap(shake, chunk, new_modules, f)
            f.close()
            os._exit(0)
        else:
            print("Parent: created child process %i." % pid)

    for i in range(0, len(chunks)):
        child_id, _ = os.waitpid(0, 0)
        print("Child process %i has finished." % child_id)

    # read all the logfile content into a string, delete the logfiles...
    logfiles = glob.glob(os.path.join(homedir, logbase + "*"))
    errors = []
    for logfile in logfiles:
        content = open(logfile, "rt").read()
        os.remove(logfile)
        if not len(content):
            continue
        errors.append(content)
    errorstring = "\n".join(errors)
    if len(errorstring):
        print("Errors:\n")
        print(errorstring)


if __name__ == "__main__":
    main()
