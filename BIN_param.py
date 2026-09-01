#!/usr/bin/env python3

"""
Read PARM messages from a dataflash file and write them to a params file.
"""

from argparse import ArgumentParser
from operator import attrgetter

from pymavlink import mavutil

import util
from tlog_param import (
    NOISY_PARAMS,
    EK3_SRCn_POSXY,
    EK3_SRCn_POSZ,
    EK3_SRCn_VELXY,
    EK3_SRCn_VELZ,
    EK3_SRCn_YAW,
)


class DataflashParam:
    def __init__(self, msg):
        self.time_us = msg.TimeUS
        self.id = msg.Name
        self.value = msg.Value
        self.when = f"[{self.time_us:12d}]"

    def is_int(self) -> bool:
        return isinstance(self.value, (int, float)) and float(self.value).is_integer()

    def value_int(self) -> int:
        return int(self.value)

    def value_str(self) -> str:
        if self.is_int():
            return str(int(self.value))
        return f"{self.value:.6f}"

    def comment(self) -> str | None:
        if self.id.startswith("EK3_SRC"):
            if self.id.endswith("POSXY"):
                return EK3_SRCn_POSXY.get(int(self.value), None)
            elif self.id.endswith("VELXY"):
                return EK3_SRCn_VELXY.get(int(self.value), None)
            elif self.id.endswith("POSZ"):
                return EK3_SRCn_POSZ.get(int(self.value), None)
            elif self.id.endswith("VELZ"):
                return EK3_SRCn_VELZ.get(int(self.value), None)
            elif self.id.endswith("YAW"):
                return EK3_SRCn_YAW.get(int(self.value), None)
            elif self.id == "EK3_SRC_OPTIONS":
                return "FuseAllVelocities" if int(self.value) == 1 else "None"
        return None


def print_change(old_param: DataflashParam | None, new_param: DataflashParam | None):
    """
    Note the change
    """
    param_id = new_param.id if new_param else old_param.id
    if param_id in NOISY_PARAMS:
        return

    param_when = new_param.when if new_param else "REMOVED"

    if old_param:
        old_param_str = f"{old_param.value_int()}" if old_param.is_int() else f"{old_param.value:.6f}"
    else:
        old_param_str = "ADDED"

    if new_param:
        new_param_str = f"{new_param.value_int()}" if new_param.is_int() else f"{new_param.value:.6f}"
    else:
        new_param_str = ""

    print(f"{param_when} {param_id:18s} {old_param_str} -> {new_param_str}")


def print_changes(previous_file: "DataFlashParams", current_file: "DataFlashParams"):
    """
    Compare to a previous BIN file
    """
    if not len(previous_file.params) and not len(current_file.params):
        print("Nothing to compare")
        return

    # Print UNSET -> param and param -> param
    for _, param in sorted(current_file.params.items()):
        if param.id not in previous_file.params:
            print_change(None, param)
        elif param.value != previous_file.params[param.id].value:
            print_change(previous_file.params[param.id], param)

    # Print param -> UNSET
    for _, param in sorted(previous_file.params.items()):
        if param.id not in current_file.params:
            print_change(param, None)


class DataFlashParams:
    """
    Keep all copies of parameters for write_params_file, and a dictionary of latest parameters.
    """

    def __init__(self, interesting: list[str] | None = None):
        self.interesting = interesting
        self.param_list: list[DataflashParam] = []
        self.params: dict[str, DataflashParam] = {}

    def add(self, msg):
        if self.interesting is None or msg.Name in self.interesting:
            param = DataflashParam(msg)
            self.param_list.append(param)
            self.params[param.id] = param

    def write_params_file(self, outfile: str):
        if not len(self.param_list):
            print("Nothing to write")
            return

        print(f"Writing {outfile}")
        f = open(outfile, "w")

        previous_id = None
        for param in sorted(self.param_list, key=attrgetter("id", "time_us")):  # Sort by id, then by time
            s = f"{param.id:20s}{param.time_us:12}"
            s = s + (" >>>" if param.id == previous_id else "    ")
            s = s + f"{param.value:30}"
            comment = param.comment()
            if comment is not None:
                s = s + f"  # {comment}"

            f.write(s + "\n")
            previous_id = param.id

        f.close()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-r", "--recurse", help="enter directories looking for BIN files", action="store_true")
    parser.add_argument(
        "-c", "--changes", help="only show changes across files, do not write *.params files", action="store_true"
    )
    parser.add_argument(
        "-p",
        "--params",
        help="track only these parameters, comma separated list of parameter names",
        type=str,
        default=None,
    )
    parser.add_argument("path", nargs="+")
    args = parser.parse_args()
    files = util.expand_path(args.path, args.recurse, ".BIN")
    print(f"Processing {len(files)} files")

    params_to_track = None if args.params is None else args.params.split(",")

    previous_file = None
    for file in files:
        print("-------------------")
        print(f"Reading {file}")
        mlog = mavutil.mavlink_connection(file, robust_parsing=False, dialect="ardupilotmega")

        current_file = DataFlashParams(params_to_track)

        while (msg := mlog.recv_match(blocking=False, type=["PARM"])) is not None:
            current_file.add(msg)

        # If --changes is True, then print changes between files, but not changes w/in files
        if args.changes:
            if previous_file is not None:
                print_changes(previous_file, current_file)
            previous_file = current_file
        else:
            current_file.write_params_file(util.get_outfile_name(file, ext=".params"))


if __name__ == "__main__":
    main()
