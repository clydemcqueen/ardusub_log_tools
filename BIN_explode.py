#!/usr/bin/env python3

"""
Read ArduSub dataflash messages from a BIN file and write a csv file for each message type.

This is a wrapper around BIN_merge.py that calls BIN_merge.py with the --no-merge and --explode flags.
"""

import sys
from BIN_merge import main

if __name__ == '__main__':
    # Add --no-merge and --explode to the arguments
    sys.argv.insert(1, '--no-merge')
    sys.argv.insert(2, '--explode')
    main()
