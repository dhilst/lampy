import sys
sys.setrecursionlimit(100)
from typing import Tuple
from ast import parse, fix_missing_locations, Expression, NodeTransformer, parse # type: ignore
from astlib import lazy, unify, match
from letast import matchdec


class Foo:
    foo = 1


x = Foo()


#@matchdec
#def fact(n):
#    return match(n, { 0: 1, v: v * fact(v - 1) })

#@matchdec
#def getfoo1(f):
#    return match(f, { Foo(foo=_foo) : _foo, _: 0 })



from astlib import match
def fact(n):
    return match(n,
        (0,   lambda: 1),
        ("x", lambda x: x * fact(x - 1))
    )

match(Foo(), ("Foo(x=1)", lambda obj: print("foo is", obj)))

print(fact(5))
