import sys
import argparse


def parse_args(args, ver):

    parser = argparse.ArgumentParser()

    parser.add_argument('-b', '--backup', action='append',
                        help='<Required> List of Devices to Backup', required=True)

    # Optional argument which requires a parameter (eg. -d test)
    parser.add_argument("-n", "--name", default='sebs',
                        help='<Optional> specify a your app name.')

    # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="Verbosity (-v, -vv, etc)")

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=ver))

    if len(args) == 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    parsed_args = parser.parse_args(args)

    parsed_args.name = parsed_args.name if 'sebs' in parsed_args.name else f'{parsed_args.name}-sebs'

    print(f'x{parsed_args.name}x')

    print(parsed_args)

    return parsed_args
