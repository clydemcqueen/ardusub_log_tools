#!/bin/bash

# To reproduce this bug: https://github.com/ArduPilot/pymavlink/issues/807
mavlogdump.py --quiet --types DISTANCE_SENSOR 2023-04-18\ 11-03-34.tlog
