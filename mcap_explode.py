#!/usr/bin/env python3

"""
Read MAVLink messages and BlueOS extension logs from an MCAP file and write a csv file for each message type.

This is a wrapper around mcap_merge.py that calls mcap_merge.py with the --no-merge and --explode flags.

Supports segments.
"""

import sys

from mcap_merge import main

if __name__ == "__main__":
    # Add --no-merge and --explode to the arguments
    sys.argv.insert(1, "--no-merge")
    sys.argv.insert(2, "--explode")
    main()
