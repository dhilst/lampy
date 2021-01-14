#!/usr/bin/env python3
import sys
from letparser import parse
import astlib

if __name__ == "__main__":
    f = sys.argv[1]
    sys.argv = sys.argv[1:]
    globals_ = {
        'match': astlib.match,
        '_': None,
    }
    parse(open(f).read()).eval(globals=globals_)
