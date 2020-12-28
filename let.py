#!/usr/bin/env python3
import sys
from letparser import parse

if __name__ == "__main__":
    parse(open(sys.argv[1]).read()).eval()
