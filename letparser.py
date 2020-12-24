import re
import io
import astlib
from collections.abc import Iterable
from lark import Lark, Transformer as LarkTransformer, Token
from typing import *
from functools import wraps

Buffer = io.BufferedIOBase
Result = Optional[Tuple[Any, Buffer, Callable[[Any, Buffer], Any]]]
RegexResult = tuple[re.Match, Buffer, callable]
Token = tuple[str, str]  # (type, value)

grammar = """
    ?start : let
    ?let : "let" (arg|kwarg) "in" let | expr
    arg : ID
    kwarg : arg "=" let
    ?expr : ifternary
    ifternary : let "if" boolexpr "else" let | boolexpr
    ?boolexpr : boolexpr BOOL_OP let | aritexpr
    ?aritexpr : aritexpr OP call | call
    ?call: atom callargs+ | atom
    callargs : "(" (let ("," let)* )* ")"
    ?atom: FQID | ID | const | "(" let ")"
    const : bool | signed_number | escaped_string
    signed_number: SIGNED_NUMBER
    escaped_string : ESCAPED_STRING
    bool : BOOL
    BOOL_OP : "==" | ">=" | ">" | "<" | "<=" | "or" | "and"
    FQID : ID "." ID+
    OP : "+" | "-" | "*" | "/"
    BOOL : "true" | "false"

    %import common.WS
    %import common.SIGNED_NUMBER
    %import common.ESCAPED_STRING
    %import common.CNAME -> ID
    %import common.SH_COMMENT
    %ignore WS
    %ignore SH_COMMENT
"""

let_parser = Lark(grammar, parser="lalr")


def parse(input_):
    res = let_parser.parse(input_)
    res = Transmformator().transform(res)
    return res


class Transmformator(LarkTransformer):
    def kwarg(self, tree):
        rest = tree[1][0] if isinstance(tree, Iterable) and len(tree) > 1 and isinstance(tree[1], list) else tree[1]
        return { tree[0][0]: rest }

    def arg(self, tree):
        return [tree[0].id]

    def let(self, tree):
        e = tree[1][0] if isinstance(tree[1], list) and len(tree[1]) >= 1 else tree[1]
        if isinstance(tree[0], dict):
            return astlib.let(**tree[0])(e)
        return astlib.letargs(*tree[0])(e)

    def ID(self, tree):
        if hasattr(tree, "value") and tree.value in ("true", "false"):
            from ast import Constant
            return Constant("true" == tree.value)
        return astlib.name(tree[0])

    def FQID(self, tree):
        return astlib.name(".".join(t.id for t in tree))

    def OP(self, tree):
        from ast import Add, Sub, Mult, Div, FloorDiv, Mod, Pow
        token = tree[0]
        opmap = {
                "+": Add,
                "-": Sub,
                "*": Mult,
                "/": Div,
                }
        return opmap[token]()

    def boolexpr(self, tree):
        from ast import Compare
        return Compare(tree[0], [tree[1]], comparators=[tree[2]])


    def infix(self, tree):
        from ast import BinOp
        left = tree[0]
        if isinstance(left, list):
            left = left[0]
        right = tree[2]
        if isinstance(right, list):
            right = right[0]
        res = BinOp(left, tree[1], right)
        return res

    def call(self, tree):
        name, *args = tree
        call = astlib.call(name, *args[0][1:])
        for a in args[1:]:
            call = astlib.call(call, *a[1:])
        return call

    def callargs(self, tree):
        return ("callargs", *tree)

    def BOOL_OP(selfm, tree):
        from ast import BoolOp, Eq, NotEq, Lt, LtE, Gt, GtE, Is, IsNot, In, NotIn
        objmap = {
            "==": Eq,
            "!-": NotEq,
            "<": Lt,
            ">": Gt,
            "<=": LtE,
            ">=": GtE,
            "is": Is,
            "is not": IsNot,
            }
        return objmap[tree]()

    def const(self, tree):
        return tree[0]

    def signed_number(self, tree):
        return astlib.const(float(tree[0].value))

    def ifternary(self, tree):
        if len(tree) == 1:
            return tree[0]
        from ast import IfExp
        return IfExp(tree[1], tree[0], tree[2])

    def aritexpr(self, tree):
        from ast import BinOp
        return BinOp(tree[0], tree[1], tree[2])

    def bool(self, tree):
        if tree[0].value == "true":
            return astlib.e("True")
        elif tree[0].value == "false":
            return astlib.e("False")
        else:
            raise ValueError(f"{tree[0]} is not true|false")


