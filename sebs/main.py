#!/usr/bin/env python3
"""
Module Docstring
"""

__authors__ = ["Levi Blaney", "Neha Singh"]
__version__ = "0.1.0"
__license__ = "GPLv3"

import sys
import argparse
from ec2 import Instance


def main(args):
    """ Main entry point of the app """
    print("hello world")
    print(args)

    # Get a handler for the current EC2 instance
    server = Instance()

    # Add the requested Stateful Devices to the server
    for device in args.backup:
        server.add_stateful_device(device)

    # Make sure the Stateful Volumes are attached to this server
    server.attach_stateful_volumes()

    # Tag the Stateful Volumes so they can be found on next boot
    server.tag_stateful_volumes()

    # I think we done?

    sys.exit()


if __name__ == "__main__":
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser()

    parser.add_argument('-b', '--backup', action='append',
                        help='<Required> List of Devices to Backup', required=True)

    # Optional argument which requires a parameter (eg. -d test)
    parser.add_argument("-n", "--name", default='sebs',
                        help='<Optional> specify a unique name.')

    # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity (-v, -vv, etc)")

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__))

    args = parser.parse_args()
    main(args)
