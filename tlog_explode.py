#!/usr/bin/env python3

"""
Read MAVLink messages from a tlog file (telemetry log) and write a csv file for each message type.

This is a wrapper around tlog_merge.py that calls tlog_merge.py with the --no-merge and --explode flags.

Supports segments.
"""

import sys
from tlog_merge import main

if __name__ == '__main__':
    # Add --no-merge and --explode to the arguments
    sys.argv.insert(1, '--no-merge')
    sys.argv.insert(2, '--explode')
    main()