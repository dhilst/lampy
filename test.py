#!/usr/bin/env python3
import sys
import doctest
import unittest

from lampy import lampy, utils, parser


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(lampy))
    tests.addTests(doctest.DocTestSuite(utils))
    return tests


class Test(unittest.TestCase):
    def test_parse(self):
        return
        print(
            parser.lamb_parser.parse(
                """
            (a);
            (a b);
            a b c d;

            (x y => x) 1 2;
            x => x;
            x y z => x z (y z);

            a b => a + b;
            a b => a + b * a;
            a b => a * b + a;

            a b c => a b + c;
            a b c => a (b + c);
        """
            ).pretty()
        )

        input_ = """
        (a b => a + b) 1 2;
        """
        stmts = parser.parse(input_)

        self.assertEqual(3, stmts[0].eval())
