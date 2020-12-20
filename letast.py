import importlib
import inspect
import sys
import types
from typing import *
from ast import (
    AST,
    NodeTransformer,
    arguments,
    arg,
    Lambda,
    parse,
    In,
    Call,
    Expression,
    fix_missing_locations,
    keyword,
    dump,
)
from functools import partial

dump = partial(dump, indent=4)


def arguments(
    posonlyargs=[],
    args=[],
    varg=arg("args"),
    kwonlyargs=[],
    kw_defaults=[],
    kwarg=arg("kwargs"),
    defaults=[],
):
    return arguments(
        posonlyargs=posonlyargs,
        arg=args,
        varg=varg,
        kwonlyargs=kwonlyargs,
        kw_defaults=kw_defaults,
        kwarg=kwarg,
        defaults=defaults,
    )


def create_args(keywords):
    return arguments(
        posonlyargs=[],
        args=[arg(k.arg) for k in keywords],
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[],
    )


def create_let_lamb(call, body):
    return Lambda(
        args=_arguments(
            args=[arg(arg=a.id) for a in call.args],
        ),
        body=body,
    )


def create_let_call(call, body):
    if call.args:
        if call.keywords:
            raise SyntaxError(
                "Can't have keywords and non-keywords arguments at same let call"
            )
        return create_let_lamb(call, body)
    args = create_args(call.keywords)
    lamb = Lambda(args, body=body)
    kwds = [keyword(k.arg, k.value) for k in call.keywords]
    return Call(lamb, args=[], keywords=kwds)


class LetVisitor(NodeTransformer):
    def visit_Compare(self, node):
        """
        Trasnlates to lamba calls

        let (M=N) in O
            => (lambda M: O)(M=N)

        let (M=N) in let (P=Q) in O
            => (lambda M: (lambda P: O)(P=Q))(M=N)
        """
        if node.left.func.id in ("let", "match") and isinstance(node.ops[0], In):
            self.visit(node.comparators[0])
            if node.left.func.id == "let":
                if len(node.comparators) > 1:
                    body = node.comparators[-1]
                    for call_ in node.comparators[:-1]:
                        call = create_let_call(call_, body)
                        body = call
                    call = create_let_call(node.left, call)
                else:
                    call = create_let_call(node.left, node.comparators[0])
                return fix_missing_locations(call)
            elif node.left.func.id == "match":
                __import__("ipdb").set_trace()
        return node

    def visit_FunctionDef(self, node):
        found = None
        node.decorator_list = list(
            filter(lambda d: d.id != "letdec", node.decorator_list)
        )
        self.generic_visit(node)
        return node


def letdec(f):
    source = inspect.getsource(f)
    old_code_f = f.__code__
    old_ast = parse(source)
    new_ast = fix_missing_locations(LetVisitor().visit(old_ast))
    new_code_obj = compile(new_ast, old_code_f.co_filename, "exec")
    new_f = types.FunctionType(new_code_obj.co_consts[0], f.__globals__)
    return new_f


def letfy_module(modpath):
    import re

    source = re.sub(r"(?<=in)\s*\r?\n", "", open(modpath).read())
    old_ast = parse(source)
    new_ast = fix_missing_locations(LetVisitor().visit(old_ast))
    new_code_obj = compile(new_ast, modpath, "exec")
    exec(new_code_obj)
    return new_code_obj


# print(foo())  # => 10

print(dump(e("a + 1")))
