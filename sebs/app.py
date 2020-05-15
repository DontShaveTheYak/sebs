#!/usr/bin/env python3
"""
Module Docstring
"""

__authors__ = ["Levi Blaney", "Neha Singh"]
__version__ = "0.1.0"
__license__ = "GPLv3"

import sys
from sebs.cli import parse_args
from sebs.ec2 import Instance


def main(args):

    # Get a handler for the current EC2 instance
    server = Instance(args.name)

    print(f'Running on {server.instance.instance_id}')

    # Add the requested Stateful Devices to the server
    for device in args.backup:
        server.add_stateful_device(device)

    # Make sure the Stateful Volumes are attached to this server
    server.attach_stateful_volumes()

    # Tag the Stateful Volumes so they can be found on next boot
    server.tag_stateful_volumes()

    for sv in server.backup:
        print(f"{sv.device_name} is {'Ready' if sv.ready else 'not Ready'} ")

    # I think we done?
    print('All done')
    sys.exit()


if __name__ == "__main__":
    args = parse_args(sys.argv[1:], __version__)
    main(args)
