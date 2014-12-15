""" A module for expanding meta ini files into sets of ini files.

This module provides methods to expand a meta ini files into a set
of corresponding ini files. The meta ini file format is defined as
follows.

- The syntax of a regular ini file with "=" as assignment operator for
  key/value pairs is entirely valid. Every ini file is also a meta ini file.
- A user can use an arbitrary amount of additional assignment operators.
  These must be of the form "=<type>=", where <type> is any string identifying
- Such custom assignment operators are followed by a comma separated list of
  values instead of a single value. All assignments using the same operator
  must use the same number of values.
- For each assignment operator present in the meta ini file <n> sets of key/value pairs
  are generated, where <n> is the number of entries in the lists after that
  assignment operator.
- The sets of key/value pairs from different assignment operators are combined
  to larger set by taking the cartesian product of the individual sets.
- The assignment operator "==" (<type> is empty) is special, in the sense,
  that it will always build a product, even with other key/value pairs using "=="
- You can have values depending on other key/value pairs. The syntax for such dependency
  is having a key (use dots for nested keys) in curly brackets inside the value.
  Those values are replaced by the actual value after expanding the meta ini file
  into the set of ini files.
- The output ini files use the meta ini name as a base name. By default, an
  increasing number is appended to the basename.
- You can also set a custom name for the generated ini file by setting the
  reserved key "__name" in your meta ini file and use the {} syntax for meaningful naming.

This is an example aiming at showing the full power of the meta ini syntax:

==== START example
__name = {model.parameters}_gridlevel{grid.level}

[grid]
level =grid= 3, 4, 5
screenOutput =grid= 1, 0, 0 #screen output for level >= 4 kills me

[model]
parameters == simple, complex
==== END example

The example produces a total of 6 ini files.

Known issues:
- The characters '=', ',',' {','}','[' and ']' should neither appear in keys nor in values.
- the code could use a lot more error checking

Known bugs:
- Having special assignment and a subgrouping by keyname in the same line is broken, if that
subgroup is not used elsewhere. THe reason is that the dictionary "normal" doesnt pick it up
correctly.
"""

from escapes import *
from parseIni import parse_ini_file
from copy import deepcopy

def expand_meta_ini(filename, assignment="=", subgroups=True):
    """ take a meta ini file and construct the set of ini files it defines

    Arguments:
    ----------
    filename : string
        The filename of the meta ini file
        
    Keyword Arguments:
    ------------------
    assignment : string
        The standard assignment operator
    subgroups : bool
        Whether the meta ini file interprets dots in groups as subgroups
    """

    # one dictionary to hold the results from several parser runs
    # the keys are all the types of assignments occuring in the file
    # except for normal assignment, which is treated differently.
    result = {}

    # we always have normal assignment
    normal = parse_ini_file(filename, assignment=assignment, asStrings=True, subgroups=subgroups)

    # look into the file to determine the set of assignment operators used
    file = open(filename)
    for line in file:
        if count_unescaped(line, assignment) is 2:
            key, assignChar, value = escaped_split(line, assignment)
            result[assignChar] = {}

    # get dictionaries for all sorts of assignments
    for key in result:
        assignChar = "{}{}{}".format(assignment, key, assignment)
        result[key] = parse_ini_file(filename, assignment=assignChar, asStrings=True, subgroups=subgroups)

    # start combining dictionaries - there is always the normal dict
    configurations = [normal]

    def generate_configs(d, configurations, prefix=[]):
        def configs_for_key(key, vals, configs, prefix):
            for config in configs:
                for val in vals:
                    c = deepcopy(config)
                    pos = c
                    for p in prefix:
                        pos = pos[p]
                    pos[key] = val
                    yield c

        for key, values in d.items():
            if type(values) is dict:
                pref = prefix + [key]
                configurations = generate_configs(values, configurations, pref)
            else:
                values = escaped_split(values, ',')
                configurations = configs_for_key(key, values, configurations, prefix)

        for config in configurations:
            yield config

    # do the all product part associated with the == assignment
    if "" in result:
        configurations = [l for l in generate_configs(result[""], configurations)]

    def expand_dict(d, output=None, prefix=[]):
        """ expand the dictionary of one assignment operator into a set of dictionary
            containing the actual key value pairs of that assignment operator """
        for key, values in d.items():
            if type(values) is dict:
                pref = prefix + [key]
                output = expand_dict(values, output, pref)
            else:
                values = escaped_split(values, ',')
                if output is None:
                    output = [{} for i in range(len(values))]
                for index, val in enumerate(values):
                    mydict = output[index]
                    for p in prefix:
                        if p not in mydict:
                            mydict[p] = {}
                        mydict = mydict[p]
                    mydict[key] = val

        return output

    def join_nested_dicts(d1, d2):
        """ join two dictionaries recursively """
        for key, item in d2.items():
            if type(item) is dict:
                d1[key] = join_nested_dicts(d1[key], item)
            else:
                d1[key] = item
        return d1

    # do the part for all other assignment operators
    for assign, tree in result.items():
        # ignore the one we already did above
        if assign is not "":
            expanded_dict = expand_dict(tree)

            newconfigurations = []

            # combine the expanded dictionaries with the ones in configurations
            for config in configurations:
                for newpart in expanded_dict:
                    # newconfigurations.append(dict(config.items() + newpart.items()))
                    newconfigurations.append(join_nested_dicts(deepcopy(config), newpart))

            configurations = newconfigurations

    # resolve all key-dependent names present in the configurations
    for c in configurations:

        def needs_resolution(d):
            """ whether curly brackets can be found somewhere in the dictionary d """
            for key, value in d.items():
                if type(value) is dict:
                    if needs_resolution(value) is True:
                        return True
                else:
                    if ("{" in value) and ("}" in value):
                        return True
            return False

        def dotkey(d, key):
            """ Given a key containing dots, return the value from a nested dictionary """
            if "." in key:
                group, key = key.split(".", 1)
                return dotkey(d[group], key)
            else:
                return d[key]

        def resolve_key_dependencies(fulldict, processdict):
            """ replace curly brackets with keys by the appropriate key from the dictionary - recursively """
            for key, value in processdict.items():
                if type(value) is dict:
                    resolve_key_dependencies(fulldict, value)
                else:
                    while (exists_unescaped(value, "}")) and (exists_unescaped(value, "{")):
                        # split the contents form the innermost curly brackets from the rest
                        # TODO use regexp and escaping here. This would require a regexp for this rsplit... ugly!!!
                        begin, dkey = value.rsplit("{", 1)
                        dkey, end = dkey.split("}", 1)

                        # check for the special key that deletes the entire key.
                        if dkey == "__delete":
                            del processdict[key]
                            value = ""
                        else:
                            newvalue = ""
                            # check for and apply the special key __lower
                            if dkey.startswith("__lower"):
                                rest, dkey = dkey.split(".", 1)
                                newvalue = dotkey(fulldict, dkey).lower()
                            # check for and apply the special key __upper
                            if dkey.startswith("__upper"):
                                rest, dkey =  dkey.split(".", 1)
                                newvalue = dotkey(fulldict, dkey).upper()
                            # if none of the above happened:
                            if newvalue is "":
                                newvalue = dotkey(fulldict, dkey)

                            # substitute the key by the correct value
                            processdict[key] = begin + newvalue + end
                            value = processdict[key]

        # values might depend on keys, whose value also depend on other keys.
        # In a worst case scenario concerning the order of resolution,
        # a call to resolve_key_dependencies only resolves one such layer.
        # That is why we need to do this until all dependencies are resolved.
        while needs_resolution(c) is True:
            resolve_key_dependencies(c, c)

    # write the configurations to disk

    # count the number of occurences of __name keys in the data set
    name_dict = {}
    for c in configurations:
        if "__name" in c:
            if c["__name"] not in name_dict:
                name_dict[c["__name"]] = 1
            else:
                name_dict[c["__name"]] += 1

    # now delete all those keys that occure once and reset all others to a counter
    for key, value in name_dict.items():
        if value is 1:
            del name_dict[key]
        else:
            name_dict[key] = 0

    # initialize a counter in the case of number only file name generation
    counter = 0
    base, extension = filename.split(".", 1)
    for conf in configurations:
        # check whether a custom name has been provided by the user
        if "__name" in conf:
            conffile = conf["__name"]
            if conf["__name"] in name_dict:
                conffile += "_" + str(name_dict[conf["__name"]]).zfill(4)
                name_dict[conf["__name"]] += 1
            # update the name key in the configuration dictionary
            conf["__name"] = conffile + ".ini"
        else:
            conf["__name"] = base + str(counter).zfill(4)+ ".ini"
            counter = counter + 1

    return configurations