#!/usr/bin/env python

# stdlib imports
import os.path
import argparse

# local imports
from shakemap_modules.utils.config import check_all_configs, get_config_paths


TAB = "  "


def _print_issue(issue, ntabs):
    """Recursively iterate over issue dictionary and print errors."""
    for key, value in issue.items():
        if isinstance(value, dict):
            tabs = TAB * ntabs
            print(f"{tabs}{key} (section):")
            ntabs += 1
            print_issue(value, ntabs=ntabs)
        elif isinstance(value, bool):
            if value == False:
                tabs = TAB * ntabs
                print(f"{tabs}{key} parameter is missing.")
            continue
        else:
            tabs = TAB * ntabs
            print(f"{tabs}{key} (parameter):")
            tabs = TAB * (ntabs + 1)
            print(f"{tabs}{value}")


def main():
    description = """Check configuration files in current profile against specifications.

Missing parameters, parameters with the wrong data type (integer, float, string, and so on) will
be flagged. Configuration files for which there are specification files will also be flagged,
but note that this may not be a problem if the functionality specified by the configuration
is not required for the user's installation of ShakeMap.
"""
    parser = argparse.ArgumentParser(description=description)
    args = parser.parse_args()
    install_path, _ = get_config_paths()
    configdir = os.path.join(install_path, "config")
    missing, issues, exceptions = check_all_configs(configdir)
    print()
    if len(missing):
        msg = (
            "The following configuration files are not present.\n"
            "Note that this may not be an issue if the configuration file\n"
            "is not required for your installation:\n"
        )
        print(msg)
        for mfile in missing:
            print(f"  {mfile}")
        print()
    for specfile, issue in issues.items():
        print(f"{specfile} (file):")
        _print_issue(issue, 1)
        print()


if __name__ == "__main__":
    main()
