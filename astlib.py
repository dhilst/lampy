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
    NodeVisitor,
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
        if m == "_":
            return expr()
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


def attrs(obj, *attrs):
    for a in attrs:
        try:
            return getattr(obj, a)
        except AttributeError:
            pass
    return obj


class SimplifyVisitor(NodeTransformer):

    def visit_Call(self, node):
        self.generic_visit(node)
        res = ("call", node.func[1], tuple(attrs(b, "value", "id") for a, b in zip(node.args[0::2], node.args[1::2])), { k.arg: attrs(k.value, "value", "id") for k in node.keywords })
        return res

    def visit_Tuple(self, node):
        self.generic_visit(node)
        n = node.elts
        return ("tuple", *zip(n[0::2], n[1::2]))

    def visit_Name(self, node):
        return ("name", node.id)

    def visit_Constant(self, node):
        return ("constant", node.value)

    def visit_Starred(self, node):
        self.generic_visit(node)
        return ("starred", node.value)

    def visit_List(self, node):
        self.generic_visit(node)
        if len(node.elts) == 0:
            return ("empty", None)
        return ("list", node.elts)

def _get(a, attr):
    try:
        return a[attr]
        return getattr(a, attr)
    except:
        pass

class get:
    def __init__(self, attr):
        self.attr = attr

    def __rlshift__(self, other):
        return _get(other, self.attr)


def unify_call(value, fname, args, kwargs, *, locals_={}):
    captured_args = {}
    # F(a=b)      |> isinstance(value, F) and hasattr(value, a) and getattr(value, a) == b
    # F(a=B)      |> isinstance(value, F) and hasattr(value, a) and isinstance(getattr(value, a), B) and B
    # F(a=B(c=d)) |> isinstance(value, F) and getattr(value, a) and isinstance(getattr(value, a), B) and
    if value is None:
        return None

    klass = locals_.get(fname)
    if klass is None:
        print(f"Can't find class {fname} in locals", file=sys.stderr)
        return None

    if not isinstance(value, klass):
        return None

    for a in args:
        # Test F(a) |> getattr(F(), a)
        if (attr := getattr(value, a, None)) is not None:
            captured_args.update({ a: attr })
        else:
            return None

    for k, v  in kwargs.items():
        token, *args = v
        if token == "call": # in F(a=B(c=d)) we are in B
            token, fname, args, kwargs = v
            if (u := unify_call(getattr(value, k, None), fname, args, kwargs, locals_=locals_)) is not None:
                captured_args.update(u)
            else:
                return None
        elif token == "constant":
            if (attr := getattr(value, k, None)) is not None and attr != args[0]:
                return None

    return captured_args

def unify_tuple(value, tree, s, *, locals_={}):
    capt_vars = {}

    if not isinstance(value, Iterable):
        return None

    if isinstance(value, (list, tuple)):
        value = iter(value)

    for i, (token, tk_value) in enumerate(tree[1:]):
        if token == "name":
            if (v := next(value, None)) is not None:
                if tk_value != "_":
                    capt_vars.update({ tk_value: v })
            else:
                return None
        elif token == "starred":
            capt_vars.update({ tk_value[1]: list(value) })
        elif token == "constant":
            if next(value, None) != tk_value:
                return None
    return { **s, **capt_vars }


def unify(value, pattern, s={}, *, locals_={}):
    from collections.abc import Iterable
    from ast import Tuple
    import re

    # unify variables "x"
    tree = SimplifyVisitor().visit(e(pattern))
    token, *args = tree
    if token == "name":
        return { **s , args[0]: value }
    elif token == "call":
        fname, args, kwargs = args
        if (res := unify_call(value, fname, args, kwargs, locals_=locals_)) is not None:
            return { **s, **res }
        else:
            return None
    elif token == "tuple":
        return unify_tuple(value, tree, s, locals_=locals_)
    elif token == "empty":
        if next(iter(value), None) is not None:
            return None
        else:
            return { **s }
    elif token == "constant":
        if value == args[0]:
            return { **s }
        else:
            return None


# print(Let().let(a=const(1)).nin(e("a + 1")).eval())
