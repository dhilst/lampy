import sys
from typing import Tuple
from ast import parse, fix_missing_locations, Expression, NodeTransformer, parse # type: ignore
from astlib import lazy, unify, match
from letast import matchdec

def sum(*values):
    return match(values,
            ("[]", lambda: 0),
            ("a, *b", lambda a, b: a + sum(*b)))


def fact(n):
    return match(n,
            ("0", lambda: 1),
            ("n", lambda n: n * fact(n-1)))

def map_(cb, it):
    return match(it,
            ("[]", lambda: []),
            ("a, *b", lambda a, b: [cb(a)] + map_(cb, b)))


class Bar:
    bar = 1

class Foo:
    bar = Bar()
    zar = "hello"

match(Foo(),
    # object destruction
    ("Foo(zar, bar=Bar(bar=1))", lambda zar: print(f"{zar} pattern match")),
    ("_", lambda: print("whaever")))

print(
    match((False, False),
        ("True,_",  lambda : f"True  ?"),
        ("False,_", lambda : f"False ?"))
)


print(sum(1, 2, 3, 4))
print(fact(5))
print(map_(str.upper, ["foo", "bar"]))
