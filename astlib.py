import importlib
import inspect
import sys
import types
from typing import *
from ast import (
    AST,
    Load,
    Constant as const,
    Name,
    Module,
    NodeTransformer,
    arguments as ast_arguments,
    arg,
    Lambda,
    parse,
    In,
    Call,
    Expr,
    fix_missing_locations,
    keyword,
    dump,
)
from functools import partial

dump = partial(dump, indent=4)


AST.dump = lambda self: print(dump(self))  # type: ignore
AST.exec = lambda self: exe_expr(self)  # type: ignore


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


def lamb(*args):
    *args, e = args
    return Lambda(args=arguments(args=[arg(a) for a in args]), body=e)


def name(n, ctx=Load()):
    return Name(n, ctx=ctx)


def keywords(**kwargs):
    return [keyword(k, v) for k, v in kwargs.items()]


def call(func, *args, **kwargs):
    if isinstance(func, str):
        func = name(func)
    args = [name(arg) if isinstance(arg, str) else arg for arg in args]
    return Call(func, args=args, keywords=keywords(**kwargs))


def let(**kwargs):
    def inner(e):
        args = list(kwargs.keys()) + [e]
        return call(lamb(*args), **kwargs)

    return inner


def exe_expr(node: Expr):
    exec(
        compile(
            m(node),
            "<string>",
            "exec",
        )
    )


call(lamb("n", e("print(n)")), const(1)).exec()
let(n=const(1))(e("print(n + 1)")).exec()
