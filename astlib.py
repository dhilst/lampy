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
AST.eval = lambda self, **kwargs: _eval(self, **kwargs)
AST.compile = lambda self, **kwargs: _compile(self, **kwargs)


def _compile(e, **kwargs):
    if kwargs:
        e = call(lamb(*kwargs.keys())(e), **kwargs)

    if isinstance(e, Module):
        mode = "exec"
    else:
        mode = "eval"
        e = Expression(e)
    return compile(fix_missing_locations(e), "<string>", mode)


def _eval(e, **kwargs):
    return eval(_compile(e, **kwargs))


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


def match(name, patterns, _locals = {}):
    for m, expr in patterns:
        union = unify(name, m, locals_ = _locals)
        if union is not None:
            return call(lamb(*union.keys())(expr), **union)

    return None

def lazy(s):
    return parse(s, mode="eval").body

def unify(value, pattern, s = {}, locals_={}):
    from collections.abc import Iterable
    from ast import Tuple
    __import__('ipdb').set_trace()
    if value == pattern:
        return { **s, pattern: value }
    if isinstance(value, Constant) and isinstance(pattern, Name):
        return { **s, pattern.id: value }
    elif isinstance(value, Name) and isinstance(pattern, Constant) and locals_.get(value.id) == pattern.value:
        return { **s }
    elif isinstance(value, Name) and isinstance(pattern, Name):
        return { **s, pattern.id : value }
    elif isinstance(value, Constant) and isinstance(pattern, Constant) and value.value == pattern.value:
        return { **s }
    elif isinstance(pattern, Tuple) and isinstance(value, Tuple) and len(pattern.elts) == len(value.elts):
        tmp = {}
        for a, b in zip(value.elts, pattern.elts):
            res = unify(a, b, s)
            if res is None:
                return None
            else:
                tmp.update(res)
        return tmp
    elif isinstance(pattern, Call):
        klass_name = pattern.func.id
        klass = locals_.get(klass_name)
        if klass is None:
            return None

        elif isinstance(value, Constant):
            if getattr(value, pattern.keywords[0].arg) == pattern.keywords[0].value.value:
                return { **s, pattern.keywords[0].arg: value.value }
            else:
                return None

        elif isinstance(value, Name):
            return { **s, pattern.keywords[0].value.id: e(repr(getattr(locals_.get(value.id), pattern.keywords[0].arg))) }
    else:
        return None # unify faile:

# print(Let().let(a=const(1)).nin(e("a + 1")).eval())

