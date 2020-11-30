#!/usr/bin/env python3
import sys
import doctest
import unittest

from pyparsing import Word, nums  # type: ignore

from lampy import lampy, utils
from lampy.lampy import BNF, arit_BNF


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(lampy))
    tests.addTests(doctest.DocTestSuite(utils))
    return tests


class Test(unittest.TestCase):
    def test_bnf(self):
        BNF().runTests(
            """
           # Simple abstraction
           fn x => x y y

           # Chainned abstrxction
           fn x => fn y => x y

           # Abstraction application
           (fn x => x y) (fn x => x)

           # Try left associativity of appliction
           u v w x y z

           # Simple xpplicxtion
           (fn x => x) a

           # ɑ conversion needed
           (fn x => x y) a

           # Value
           1

           # Parenthesis
           x z (y z)

           """
        )

        arit_BNF(Word(nums)).runTests(
            """
            1 * (2 + 3)
            """
        )
