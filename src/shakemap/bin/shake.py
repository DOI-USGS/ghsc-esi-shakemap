#!/usr/bin/env python

# stdlib imports
import argparse
import importlib
import inspect
import io
import os.path
import pkgutil
import shlex
import socket
import sys
import time
import traceback
from collections import OrderedDict
import importlib
import importlib.metadata
from configobj import ConfigObj
from validate import Validator

# local imports
from esi_utils_rupture.origin import read_event_file
from shakemap.utils.dependencies import CommandDatabase
from shakemap.utils.exception import TerminateShakeMap
from shakemap_modules.utils.config import (
    config_error,
    get_config_paths,
    get_configspec,
)
from shakemap_modules.utils.logging import get_logger

VERSION = importlib.metadata.version("shakemap")
CANCEL_FILE = "CANCELED"


def _get_config():
    """
    Read the config file and return the resulting structure.
    """
    install_path, data_path = get_config_paths()
    config_file = os.path.join(install_path, "config", "shake.conf")
    spec_file = get_configspec("shake")
    config = ConfigObj(config_file, configspec=f"{spec_file}")
    results = config.validate(Validator())
    if not isinstance(results, bool) or not results:
        config_error(config, results)

    return config


def _get_command_classes(config):
    """
    Create a dictionary of classname:class to be used in main().

    Returns:
        dict: Dictionary of classname:class where each class
            is a subclass of shakemap_modules.coremods.base.CoreModule.
    """
    coremods = {}
    for modname in config["coremods"]:
        mod = importlib.import_module(modname)
        cm = {
            name: importlib.import_module(name)
            for finder, name, ispkg in pkgutil.iter_modules(
                mod.__path__, mod.__name__ + "."
            )
        }
        coremods.update(cm)

    classes = {}
    for name, module in coremods.items():
        for m in inspect.getmembers(module, inspect.isclass):
            if m[1].__module__ == name:
                core_class = getattr(module, m[0])
                if not hasattr(core_class, "command_name"):
                    continue
                cmd = core_class.command_name

                if not cmd:
                    continue
                classes[cmd] = {
                    "class": core_class,
                    "module": module,
                    "mfile": module.__file__,
                }

    ordered_classes = OrderedDict()
    for k in sorted(classes.keys()):
        ordered_classes[k] = classes[k]

    return ordered_classes


_config_ = _get_config()
_classes_ = _get_command_classes(_config_)


def _format_error_info(exception, eventid):
    """
    Format exception information and stack trace into a coherent multi-line
    string.

    Args:
        exception (Exception): Python Exception (or child thereof) instance.
        eventid (str): ShakeMap event ID (i.e., us2018abcd).
    Returns:
        str: Multiline string containing: Hostname,eventid,Exception string,
             and stack trace.

    """
    # try to get the basic earthquake info - if it fails, move on.
    eqinfo = "Not available"
    install_path, data_path = get_config_paths()
    datadir = os.path.join(data_path, eventid, "current")
    if os.path.isdir(datadir):
        datafile = os.path.join(datadir, "event.xml")
        if os.path.isfile(datafile):
            edict = read_event_file(datafile)
            mag = edict["mag"]
            loc = edict["locstring"]
            eqinfo = f"M{mag:.1f} {loc}"

    stringio = io.StringIO()
    ex_type, ex, tb = sys.exc_info()
    traceback.print_tb(tb, file=stringio)
    stack_trace = stringio.getvalue()
    stringio.close()
    hostname = socket.gethostname()
    fmt = "\nEarthquake: %s\nHost: %s\nEvent ID: %s\nException: %s\n" "Stack Trace: %s"
    error_msg = fmt % (eqinfo, hostname, eventid, str(exception), stack_trace)
    return error_msg


def get_parser():
    """
    Internal method to get argparse parser instance.

    Returns:
        ArgumentParser: argparse argument parser.
    """
    description = """
    Run specified ShakeMap modules.
    """

    epilog = "Available modules:\n"
    for key, core_class in _classes_.items():
        if key.startswith("xtest"):
            continue
        epilog += f"    - {inspect.getdoc(core_class['class'])}\n"

    epilog += (
        '\nUse "shake help command" to see the options for a ' "specific command.\n"
    )

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("eventid", help="The id of the event to process.")
    parser.add_argument("cmds", nargs=argparse.REMAINDER, help="The modules to run.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-d", "--debug", action="store_true", help="Print all informational messages."
    )
    group.add_argument("-q", "--quiet", action="store_true", help="Print only errors.")
    parser.add_argument("-l", "--log", action="store_true", help="Log all output.")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force the command(s) to run regardless of out " "of date dependencies.",
    )
    parser.add_argument(
        "-c",
        "--comment",
        help="Provide a comment for 'assemble' in "
        "this version of the ShakeMap. If the comment "
        "has spaces, the string should be quoted (e.g., "
        '--comment "This is a comment.")',
    )
    parser.add_argument(
        "-x",
        "--cancel",
        action="store_true",
        help="Cancel shakemap; execute cancel_modules list in " "shake.conf.",
    )
    group.add_argument(
        "-y",
        "--dryrun",
        action="store_true",
        help="Print a command line that would be executed if "
        "the process was called without this flag, and "
        "then exit without other action.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"ShakeMap version {VERSION}",
        help="Print the version of ShakeMap and quit.",
    )
    return parser


def main():
    """
    Loop over input commands and call module.execute() for each matching
    command.
    """
    parser = get_parser()
    args = parser.parse_args()

    if args.eventid.lower() == "help" and len(args.cmds) == 0:
        parser.print_help()
        sys.exit(0)

    install_path, data_path = get_config_paths()
    log_option = None
    log_file = None
    if args.debug:
        log_option = "debug"
    if args.quiet:
        log_option = "quiet"
    if args.log:
        log_file = "log"

    logger = get_logger(args.eventid, log_option=log_option, log_file=log_file)

    event_path = os.path.join(data_path, args.eventid, "current")
    cancel_file = os.path.join(event_path, CANCEL_FILE)
    if os.path.isfile(cancel_file):
        if _config_["process_canceled"]:
            os.remove(cancel_file)
        else:
            logger.error(f"Event {args.eventid} has been canceled: aborting run")
            return

    #
    # Build the database of commands, targets, and dependencies
    #
    cdb = CommandDatabase(_classes_, args.eventid)

    try:
        cmd_list = OrderedDict()

        # No modules were specified, go get autorun modules
        if not len(args.cmds):
            if not args.cancel:
                # cancel option was not set
                if args.dryrun is False:
                    logger.info("No modules specified, checking for autoun_modules...")
                args.cmds = shlex.split(_config_["autorun_modules"])
                if len(args.cmds):
                    if args.dryrun is False:
                        logger.info(f"Autorun modules found: {args.cmds}")
                        if args.comment:
                            logger.info(
                                f"Replacing assemble comment with: '{args.comment}'"
                            )
                else:
                    logger.warning(
                        "No modules specified, and no autorun_modules "
                        "configured. Nothing to do! -- Exiting --"
                    )
                    sys.exit(0)
            else:
                # cancel option was set
                logger.info("Cancelling shakemap, using cancel_modules...")
                with open(cancel_file, "wt") as f:
                    f.write("\n")

                args.cmds = shlex.split(_config_["cancel_modules"])
                if len(args.cmds):
                    logger.info(f"Cancel modules found: {args.cmds}")
                else:
                    logger.warning(
                        "Cancel option specified, but no cancel_modules "
                        "configured. Nothing to do! -- Exiting --"
                    )
                    sys.exit(0)

        arglist = args.cmds.copy()
        logger.debug(f"arglist: {arglist}")

        if args.dryrun is True:
            cmdlist = ""
            for item in arglist:
                if " " in item:
                    cmdlist += f"'{item}' "
                else:
                    cmdlist += item + " "
            print("Dryrun. The following command would be run:")
            print(f"shake {args.eventid} {cmdlist}")
            sys.exit(0)

        oldcmd = ""
        while len(arglist) > 0:
            cmd = arglist.pop(0)

            if cmd.startswith("-"):
                raise KeyError(f'Command "{oldcmd}" cannot process option "{cmd}"')

            if cmd not in _classes_:
                raise KeyError(f'Command "{cmd}" not found in ShakeMap.')

            cmd_class = _classes_[cmd]["class"]
            if cmd == "model":
                cmd_obj = cmd_class(args.eventid, shakemap_version=VERSION)
            else:
                cmd_obj = cmd_class(args.eventid)
            cmd_list[cmd] = cmd_obj

            if args.eventid.lower() == "help":
                arglist = ["-h"]

            # If this command is assemble, and the user has specified a comment,
            # apply it
            if "assemble" in cmd and args.comment:
                # Pop the old comment and insert the new one
                if "-c" in arglist[0]:
                    _ = arglist.pop(0)
                    _ = arglist.pop(0)
                arglist.insert(0, f"-c '{args.comment}'")

            arglist = cmd_obj.parseArgs(arglist)
            oldcmd = cmd

        for cmd, obj in cmd_list.items():
            logger.info(f"Running command {cmd}")
            status = cdb.getDependencyStatus(cmd)
            while len(status) > 0:
                if len(status) == 1 and status[0] == cmd:
                    break
                #
                # If the dependency requires select to run, but there
                # is a model.conf, then select doesn't need to be run.
                # So drop it and continue the checking process.
                #
                if status[0] == "select":
                    if os.path.isfile(os.path.join(event_path, "model.conf")):
                        status.remove("select")
                        continue
                logger.warning(
                    "Out of date dependencies. The following commands "
                    "should be rerun before '%s' (use --force to "
                    "ignore this warning and attempt to run the "
                    "module anyway):" % cmd
                )
                if cmd in status:
                    status.remove(cmd)
                logger.warning(", ".join(status))
                if not args.force:
                    logger.warning("Exiting.")
                    sys.exit(0)
                else:
                    logger.warning(f'Running "{cmd}" because of --force option.')
                break
            t1 = time.time()
            try:
                obj.execute()
            except TerminateShakeMap as e:
                logger.warning(f"ShakeMap terminated in module {cmd}: {str(e)}")
                break
            t2 = time.time()
            elapsed = t2 - t1
            logger.info(f"Finished running command {cmd}: Elapsed {elapsed:.2f} secs")
            # create/update the contents.xml file
            obj.writeContents()
            cdb.updateCommand(cmd)

    except Exception as e:
        error_msg = _format_error_info(e, args.eventid)
        logger.critical(error_msg)  # should get sent by email and logged
        sys.exit(1)

    logger.info(f"shake finished with event {args.eventid}")


if __name__ == "__main__":
    main()
