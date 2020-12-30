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
    unparse,
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
AST.eval = lambda self, **kwargs: _eval(self, **kwargs)  # type: ignore
AST.compile = lambda self, **kwargs: _compile(self, **kwargs)  # type: ignore
AST.unparse = lambda self, **kwargs: unparse(self, **kwargs)  # type: ignore


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


def match(name, *patterns: Iterator[Tuple[str, AST]], locals_=None):
    if locals_ is None:
        import inspect
        locals_ = inspect.currentframe().f_back.f_locals
    for m, expr in patterns:
        union = unify(name, m, locals_=locals_)
        if union is not None:
            if callable(expr):
                expr = expr(**union)
            elif isinstance(expr, str):
                expr = lazy(repr(expr))
            elif hasattr(expr, "eval"):
                union = { k: lazy(repr(v)) if not isinstance(k, AST) else v for k, v in union.items() }
                expr = expr.eval(**{ **locals_, **union })

            return expr

    return None


def lazy(s):
    return parse(s, mode="eval").body


def unify(value, pattern, s={}, *, locals_={}):
    from collections.abc import Iterable
    from ast import Tuple

    if type(value) == type(pattern):
        if value == pattern:
            return {**s}
        else:
            return None
    elif isinstance(pattern, str):
        import re

        __import__('pdb').set_trace()
        # unify variables "x"
        if match := re.match(r"^[a-z]$", pattern):
            return { **s , match.group(0): value }
        elif match := re.match(r"^([a-z]+)\(([^,]+(,[^,]*))\)$", pattern):
            print("class match union")
            return { **s, match.group(0): value }

    elif (
        isinstance(value, Name)
        and isinstance(pattern, Constant)
        and locals_.get(value.id) == pattern.value
    ):
        return {**s}
    elif isinstance(pattern, Name):
        if isinstance(value, Name):
            return {**s, pattern.id: value.id }
        elif isinstance(value, Constant):
            return {**s, pattern.id: value.value }
        else:
            return {**s, pattern.id: value }
    elif (
        isinstance(value, Constant)
        and isinstance(pattern, Constant)
        and value.value == pattern.value
    ):
        return {**s}
    elif (
        isinstance(pattern, Tuple)
        and isinstance(value, Tuple)
        and len(pattern.elts) == len(value.elts)
    ):
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
            if (
                getattr(value, pattern.keywords[0].arg)
                == pattern.keywords[0].value.value
            ):
                return {**s, pattern.keywords[0].arg: value.value}
            else:
                return None

        elif isinstance(value, Name):
            return {
                **s,
                pattern.keywords[0].value.id: e(
                    repr(getattr(locals_.get(value.id), pattern.keywords[0].arg))
                ),
            }
    elif isinstance(pattern, Constant):
        if pattern.value == value:
            return { **s }
    else:
        return None  # unify faile:


# print(Let().let(a=const(1)).nin(e("a + 1")).eval())
