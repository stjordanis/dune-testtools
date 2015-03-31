import command
from parseIni import parse_ini_file
from metaIni import expand_meta_ini

@command.meta_ini_command(name="some", argc=2)
def product(args=None):
    return str(int(args[0])*int(args[1]))

def test_basics():
    d = {}
    d["a"] = "CAPS | tolower"
    assert(command._registry.get("tolower", None))
    command.apply_generic_command(config=d, key="a")
    assert(d["a"] == "caps")
    #assert(command._registry["tolower"](value="CAPS", shit=0) == "caps")

def test_parsed():
    c = parse_ini_file("./tests/command.ini")
    for k in c:
        command.apply_generic_command(config=c, key=k)
    # simple operator
    assert(c["key"] == "bla")
    # double operator
    assert(c["other"] == "BLA")

def test_arguments():
    d = {}
    d["a"] = "bla | some 2 3"
    command.apply_generic_command(config=d, key="a")
    assert(d["a"] == "6")

def test_metaini():
    c = expand_meta_ini("./tests/command.ini")
    assert(len(c) == 4)
