#!/usr/bin/env python3
import sys
import doctest
from pathlib import Path
from importlib import import_module


from lampy import lampy


if __name__ == "__main__":
    options = doctest.ELLIPSIS
    for fil in Path("lampy").glob("*.py"):
        if fil.name.startswith("__"):
            continue
        mod = import_module(f"lampy.{fil.stem}")
        doctest.testmod(mod)
