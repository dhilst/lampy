import importlib
import inspect
import sys
import types
from typing import *
from ast import (
    AST,
    Load,
    Constant as const,
    Constant,
    Name,
    Module,
    NodeTransformer,
    arguments as ast_arguments,
    arg,
    Lambda,
    parse,
    In,
    Call,
    BinOp,
    Expr,
    Expression,
    fix_missing_locations,
    keyword,
    dump,
)
from functools import partial

dump = partial(dump, indent=4)


AST.dump = lambda self: print(dump(self))  # type: ignore
AST.exec = lambda self: exe_expr(self)  # type: ignore
AST.eval = lambda self, **kwargs: evl_expr(self, **kwargs)
AST.compile = lambda self: cpl_expr(self)


def cpl_expr(e, mode="eval", **kwargs):
    if kwargs:
        e = call(lamb(*kwargs.keys())(e), **kwargs)
    e = Expression(e)
    e.lineno = 1
    e.col_offset = 1
    e = fix_missing_locations(e)
    return compile(e, "<string>", mode)


def evl_expr(e, **kwargs):
    res = eval(cpl_expr(e, **kwargs))
    return res


def exe_expr(node: Expr):
    exec(
        compile(
            m(node),
            "<string>",
            "exec",
        )
    )


def arguments(
    posonlyargs=[],
    args=[],
    varg=arg("args"),
    kwonlyargs=[],
    kw_defaults=[],
    kwarg=arg("kwargs"),
    defaults=[],
):
    return ast_arguments(
        posonlyargs=posonlyargs,
        args=args,
        varg=varg,
        kwonlyargs=kwonlyargs,
        kw_defaults=kw_defaults,
        kwarg=kwarg,
        defaults=defaults,
    )


def m(*exprs):
    m = Module([Expr(e) for e in exprs], type_ignores=[])
    m.lineno = 1
    m.col_offset = 1
    m = fix_missing_locations(m)
    return m


def e(expr: str):
    return parse(expr).body[0].value  # type: ignore

def infix(op, a, b):
    return BinOp(letf=a, op=op, right=b)


def lamb(*args):
    def inner(e):
        return Lambda(args=arguments(args=[arg(a) for a in args]), body=e)

    return inner


def name(n, ctx=Load()):
    return Name(n, ctx=ctx)


def where(*args):
    def inner(expr):
        return call(expr, *args)

    return inner


def keywords(**kwargs):
    return [keyword(k, v) for k, v in kwargs.items()]


def call(func, *args, **kwargs):
    if isinstance(func, str):
        func = name(func)
    args = [name(arg) if isinstance(arg, str) else arg for arg in args]
    return Call(func, args=args, keywords=keywords(**kwargs))


def letargs(*args):
    def inner(e):
        return lamb(*args)(e)

    return inner


def let(**kwargs):
    def inner(e):
        return call(lamb(*kwargs.keys())(e), **kwargs)

    return inner


def match(var):
    def inner(arms: Dict[AST, AST]) -> AST:
        pass

    return inner


class Let:
    args = []
    kwargs = {}

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def in_(self, expr):
        if hasattr(self, "result"):
            return self.result
        self.expr = expr
        self.result = let(*self.args, **self.kwargs)(expr)
        return self.result


def astasdict(it):
    return dict(it)


# print(Let().let(a=const(1)).nin(e("a + 1")).eval())
