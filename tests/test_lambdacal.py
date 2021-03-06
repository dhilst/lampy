#!/usr/bin/env python3
import sys
import doctest
import unittest

from lampy import lampy, utils, parser, tlampy, tparser


#def load_tests(loader, tests, ignore):
#    tests.addTests(doctest.DocTestSuite(tlampy))
#    tests.addTests(doctest.DocTestSuite(lampy))
#    tests.addTests(doctest.DocTestSuite(utils))
#    return tests


class Test(unittest.TestCase):
    def test_parse(self):
        print(parser.lamb_parser.parse("f -1;").pretty())
        print(parser.lamb_parser.parse("f - 1;").pretty())
        print(parser.lamb_parser.parse("(a, b) => a -1;").pretty())
        print(parser.lamb_parser.parse("((a) => a + 10) 1 - 2;").pretty())

        def e(input_, _trace=False):
            return parser.parse(input_)[0].eval(_trace=_trace)

        self.assertEqual(3, e("((a, b) => a + b) 1 2;").val)
        self.assertEqual(2, e("((a, b) => a + b) 1 1;").val)
        self.assertEqual(1, e("((a, b) => a) 1 2;").val)
        self.assertEqual(-1, e("0 + -1;").val)
        self.assertEqual(0, e("((a) => a + 1) -1;").val)
        self.assertEqual(9, e("((a) => a + 10) 1 - 2;").val)

        # print(e("((f) => ((x) => f (x x))((x) => f (x x))) 1;"))

    def test_tparser(self):
        def e(input_, _trace=False):
            return tparser.parse(input_)[0].eval(_trace=_trace)

        def p(input_):
            return tparser.parse(input_)[0].root

        self.assertEqual(3, e("((a: int) => 1 + a) 2;").val)

        with self.assertRaises(TypeError):
           e('((a: int) => 1 + a) "2";')

        with self.assertRaises(TypeError):
           e("(a: int, b: str) => a + b;")

        self.assertEqual(
           "int -> int", repr(tparser.parse("(a: int) => a;")[0].root.typ)
        )

        self.assertEqual(
           "int -> int -> int",
           repr(tparser.parse("(a: int, b: int) => a;")[0].root.typ),
        )

        self.assertEqual(
           "int -> int -> int -> int -> int",
           repr(tparser.parse("(a: int, b: int, c: int, d: int) => a;")[0].root.typ),
        )

        self.assertEqual(
           "(int -> int) -> int -> int",
           repr(tparser.parse("(f: int -> int) => f;")[0].root.typ),
        )

        self.assertEqual(
           "int -> int",
           repr(e("((a: int, b: int) => a) 1;").typ),
        )

        self.assertEqual(
           "<class 'int'>",
           repr(
               tparser.parse("((f: int -> int, a: int) => f(a)) ((i:int) => i) 0;")[
                   0
               ].root.typ
           ),
        )

        self.assertEqual(0, e("((f: int -> int, a: int) => f a) ((i:int) => i) 0;").val)

        self.assertEqual(
           1, e("((a: int -> int, b: int) => a b) ((i: int) => i) 1;").val
        )

        self.assertEqual(
            "int -> int",
            repr(tparser.parse("((a: int, b: int) => a) 1;")[0].root.typ),
        )

        self.assertEqual(
            "(int -> int -> int) -> (int -> int) -> int -> int",
            repr(
                tparser.parse(
                    "(x: int -> int -> int, y: int -> int, z: int) => x z (y z);"
                )[0].root.typ
            ),
        )
