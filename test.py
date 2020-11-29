#!/usr/bin/env python3
import sys
import doctest
import unittest
from pathlib import Path
from importlib import import_module


from lampy import lampy, utils


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(lampy))
    tests.addTests(doctest.DocTestSuite(utils))
    return tests

