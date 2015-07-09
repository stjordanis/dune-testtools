from __future__ import absolute_import
from .parser import CommandToApply
from .metaini import expand_meta_ini
from .cmakeoutput import printForCMake
from .command import apply_commands, CommandType
from .uniquenames import *
import sys
import argparse


def extract_static_info(metaini):
    static_section = expand_meta_ini(metaini,  whiteFilter=("__STATIC", "__exec_suffix"), addNameKey=False)

    # make the found exec suffixes unique
    if "__exec_suffix" not in static_section[0]:
        static_section[0]["__exec_suffix"] = ""
    cmd = [CommandToApply(name="unique", args=[], key="__exec_suffix")]
    apply_commands(static_section, cmd)

    # determine a list of subgroups within the static section
    static_groups = []
    for conf in static_section:
        # check for __STATIC section. Who knows who may call this without having the section in the metaini-file
        if "__STATIC" in conf:
            for key in dict.__iter__(conf["__STATIC"]):
                if (isinstance(conf["__STATIC"][key], dict)) and (key not in static_groups):
                    static_groups.append(key)

    # construct a dictionary from the static information. This can be passed to CMake
    static = {}

    # The special key __CONFIGS holds a list of configuration names
    static["__CONFIGS"] = []
    # introduce a special key for all subgroups
    for group in static_groups:
        static["__" + group] = []

    for conf in static_section:
        static["__CONFIGS"].append(conf["__exec_suffix"])

        # check for key/value pairs in subgroups and add lists to the dictionary
        for group in static_groups:
            for key in conf["__STATIC"][group]:
                if key not in static["__" + group]:
                    static["__" + group].append(key)

        # copy the entire data
        if "__STATIC" in conf:
            static[conf["__exec_suffix"]] = conf["__STATIC"]

    return static


if __name__ == "__main__":
    # read command line options
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--ini', help='The meta-inifile to expand', required=True)
    args = vars(parser.parse_args())

    # call the macro
    static = extract_static_info(args["ini"])

    # print to CMake
    printForCMake(static)