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

from lampy.astlib import call, arguments, let, lamb, arguments, keywords, Let
from lampy.astlib import arguments as create_args


def create_let_lamb(call, body):
    return Lambda(
        args=arguments(
            args=[arg(arg=a.id) for a in call.args],
        ),
        body=body,
    )


def create_let_call(call_, body):
    if call_.args:
        if call_.keywords:
            raise SyntaxError(
                "Can't have keywords and non-keywords arguments at same let call"
            )
        return create_let_lamb(call_, body)
    return let(**{key.arg: key.value for key in call_.keywords})(body)


class LetVisitor(NodeTransformer):
    def visit_Compare(self, node):
        """
        Trasnlates to lamba calls

        let (M=N) in O
            => (lambda M: O)(M=N)

        let (M=N) in let (P=Q) in O
            => (lambda M: (lambda P: O)(P=Q))(M=N)
        """
        self.generic_visit(node)
        if node.left.func.id == "let" and isinstance(node.ops[0], In):
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
        return node

    def visit_FunctionDef(self, node):
        found = None
        node.decorator_list = list(
            filter(lambda d: d.id not in ("letdec", "matchdec"), node.decorator_list)
        )
        self.generic_visit(node)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        import astlib
        from ast import Call, arg, Starred, Load, Name, Tuple as ASTTuple
        if hasattr(node.func, "id") and node.func.id == "match":
            x = node.args[0]
            d = node.args[1]
            patterns = [[a, b] for a, b in zip(d.keys, d.values)]
            for p in patterns:
                if isinstance(p[0], Name):
                    p[1] = astlib.lamb()(astlib.let(**{ p[0].id: x })(p[1]))
                    p[0] = astlib.let(**{ p[0].id: x })(p[0])
                elif isinstance(p[0], Call):
                    p[1] = astlib.lamb()(astlib.let(**{ k.value.id : astlib.call("getattr", x, k.arg) for k in p[0].keywords })(p[1]))
                    p[0] = astlib.lamb()(p[0])
            patterns = ASTTuple([ASTTuple([a, b], ctx=Load()) for a, b in patterns], ctx=Load())
            res = Call(func=Name("match", ctx=Load()),
                    args=[x, patterns],
                    keywords=[])
            return res
        return node

    def visit_FunctionDef(self, node):
        found = None
        node.decorator_list = list(
            filter(lambda d: d.id != "matchdec", node.decorator_list)
        )
        self.generic_visit(node)
        return node

def matchdec(f):
    import inspect, types
    source = inspect.getsource(f)
    old_code_f = f.__code__
    old_ast = parse(source)
    locals_ = f.__globals__
    new_ast = LetVisitor().visit(old_ast)
    new_ast = fix_missing_locations(new_ast)
    new_code_obj = compile(new_ast, old_code_f.co_filename, "exec")
    new_f = types.FunctionType(new_code_obj.co_consts[0], f.__globals__)
    return new_f

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

    source = open(modpath).read()
    source = re.sub(r"(?<=in)\s*\n", "", source)
    old_ast = parse(source)
    new_ast = fix_missing_locations(LetVisitor().visit(old_ast))
    new_code_obj = compile(new_ast, modpath, "exec")
    exec(new_code_obj)
    return new_code_obj
