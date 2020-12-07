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
        print(parser.lamb_parser.parse("f -1;").pretty())
        print(parser.lamb_parser.parse("f - 1;").pretty())
        print(parser.lamb_parser.parse("(a, b) => a -1;").pretty())

        def e(input_):
            return parser.parse(input_)[0].eval()

        self.assertEqual(3, e("((a, b) => a + b) 1 2;").val)
        self.assertEqual(2, e("((a, b) => a + b) 1 1;").val)
        self.assertEqual(1, e("((a, b) => a) 1 2;").val)
        self.assertEqual(-1, e("0 + -1;").val)
        self.assertEqual(0, e("((a) => a + 1) -1;").val)
        self.assertEqual(9, e("((a) => a + 10) 1 - 2;"))
