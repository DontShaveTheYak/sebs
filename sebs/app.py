#!/usr/bin/env python3
"""
Module Docstring
"""

__authors__ = ["Levi Blaney", "Neha Singh"]
__license__ = "GPLv3"

import sys
import logging
from sebs.ec2 import Instance

log = logging.getLogger('sebs')


def main(args):

    log.info(f'Starting...')
    # Get a handler for the current EC2 instance
    server = Instance(args.name)

    # Add the requested Stateful Devices to the server
    for device in args.backup:
        server.add_stateful_device(device)

    # Make sure the Stateful Volumes are attached to this server
    server.attach_stateful_volumes()

    # Tag the Stateful Volumes so they can be found on next boot
    server.tag_stateful_volumes()

    for sv in server.backup:
        log.info(f"{sv.device_name} is {'Ready' if sv.ready else 'not Ready'}")

    log.info('Finished')
    sys.exit()
