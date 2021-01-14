import sys
from typing import Tuple
from ast import parse, fix_missing_locations, Expression, NodeTransformer, parse # type: ignore
from astlib import lazy, unify, match
from letast import matchdec

assert match("whaever", ("_", lambda : "anything")) == "anything"
assert match("1", ("'1'", lambda : "one")) == "one"

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


def zip_(a_it, b_it):
    return match(a_it,
            ("[]", lambda: []),
            ("a,*b", lambda a, b: \
                match(b_it,
                ("[]", lambda: []),
                ("c,*d", lambda c, d: [(a,c)] + zip_(b,d)))))
print(zip_([1, 2, 3],["a", "b", "c"])) # => [(1, 'a'), (2, 'b'), ...]

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


from enum import Enum
class E(Enum):
    A = 1
    B = 2
    C = 3

match(E.B,
        ("E.A", lambda : print("A")),
        ("E.B", lambda : print("B")),
        ("E.C", lambda : print("C")),
        )

try:
    match(E.B,
            ("E.A", lambda : print("A")),
            ("E.B", lambda : print("B")),
            )
except TypeError as e: # because match is not exaustive
    print(e)


