from astlib import lazy, unify, match

class Foo:
    foo = 1

x = Foo()
#x = 0

res = match(
    lazy("x"),
    (
        ( lazy("1"), lazy("0")     ),
        ( lazy("Foo(foo=n)"), lazy("n - 1") ),
    ),
    _locals=locals())


from ast import *
if res is not None:
    res.dump()
    print(eval(compile(fix_missing_locations(Expression(res)), "<string>", "eval")))

