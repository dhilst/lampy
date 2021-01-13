#!/usr/bin/env python3
import sys
from letparser import parse
from astlib import match

if __name__ == "__main__":
    f = sys.argv[1]
    sys.argv = sys.argv[1:]
    parse(open(f).read()).eval()
