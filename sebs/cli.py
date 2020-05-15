import sys
import argparse


def parse_args(args, ver):

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
        version="%(prog)s (version {version})".format(version=ver))

    if len(args) == 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser.parse_args(args)
