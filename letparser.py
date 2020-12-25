import re
import io
import astlib
from collections.abc import Iterable
from lark import Lark, Transformer as LarkTransformer, Token
from typing import *
from functools import wraps
from collections import namedtuple as nt

nt = lambda s: nt("_".join(s), s)

Buffer = io.BufferedIOBase
Result = Optional[Tuple[Any, Buffer, Callable[[Any, Buffer], Any]]]
RegexResult = tuple[re.Match, Buffer, callable]
Token = tuple[str, str]  # (type, value)

grammar = r"""
    ?start : let
    ?let : letargs | letdef | letimport | expr
    letargs : "let" (args|kwargs) "in" let
    letdef : "let" "def" ID ID* "in" expr "in" let
    ?letimport : "let" "import" fqalias ("," fqalias)* "in" let | letfromimport
    letfromimport : "let" "from" fqid "import" idalias ("," idalias)* "in" let

    args : arg+
    kwargs : kwarg+
    arg : ID
    kwarg : arg "=" let
    ?expr : doblock | ifternary

    ?doblock : "do" let (";" return )* "end"
    return : "return" let | yield
    yield  : "yield" let | let

    tupleexpr : let "," (let ("," let)*)*

    ?ifternary : let "if" boolexpr "else" let | boolexpr

    ?boolexpr : boolexpr BOOL_OP let | binopexpr
    bool : BOOL
    BOOL_OP : "==" | ">=" | ">" | "<" | "<=" | "or" | "and" | "not"
    BOOL : "True" | "False"

    ?binopexpr : binopexpr MATH_PLUS mulexpr | mulexpr
    ?mulexpr : mulexpr MATH_MUL powexpr | powexpr
    ?powexpr : integer MATH_POW powexpr | comprehensions
    MATH_PLUS: "+" | "-"
    MATH_MUL : /\*[^*]/ | "//" | "/" | "%"
    MATH_POW: "**"
    MATH_UNARY : "+" | "-"

    ?comprehensions  : listcomp
    !?listcomp        : "[" listcompexpr "]" | gencomp 
    !?gencomp         : "(" listcompexpr ")" | dictcomp
    !?dictcomp        : "{" dictcompexpr "}" | setcomp
    !?setcomp         : "{" listcompexpr "}" | call
    listcompexpr     : let         "for" (ID ("," ID)*) "in" let ("if" boolexpr ("," "if" boolexpr)*)?
    dictcompexpr     : let ":" let "for" (ID ("," ID)*) "in" let ("if" boolexpr ("," "if" boolexpr)*)?


    ?call: atom callargs+ | atom
    callargs : "(" (let ("," let)* )* ")"

    ?atom: "(" let ")" | const | fqid

    const : bool | integer | dictconst | listconst | tupleconst | setconst | STRING_CONST 
    dictconst : "{" let ":" let ("," let ":" let)* "}"
    listconst : "[" let ("," let)* "]"
    tupleconst : atom "," atom+
    setconst : "{" let ("," let)* "}"
    integer : /[+-]?\d+/ | /0x[a-fA-F]+/ | /0o[0-7]+/ | /0b[12]+/ | float
    float : /[+-]?\d+\.\d+/

    STRING_CONST.5: STRING_MODIFIER? ESCAPED_STRING

    fqalias : fqid ("as" ID)?
    idalias : ID ("as" ID)?
    fqid : ID ("." ID)+ | ID
    ID : CNAME
    STRING_MODIFIER.10 :  "f" | "r" | "b"


    %import common.WS
    %import common.ESCAPED_STRING
    %import common.CNAME
    %import common.SH_COMMENT
    %import common.INT
    %import common.NUMBER
    %ignore WS
    %ignore SH_COMMENT
"""

let_parser = Lark(grammar, parser="lalr")


def parse(input_):
    res = let_parser.parse(input_)
    print(res.pretty())
    return
    res = Transmformator().transform(res)
    return res


class Transmformator(LarkTransformer):
    def kwargs(self, tree):
        return {t.children[0].children[0].id: t.children[1] for t in tree}

    def args(self, tree):
        return [t.children[0].id for t in tree]

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
            "@": MatMulti,
            "/": Div,
            "//": FloorDiv,
            "%": Mod,
            "**": Pow,
            "<<": LShift,
            ">>": RShift,
            "|": BitOr,
            "^": BitXor,
            "&": BitAnd,
        }

        return opmap[token]()

    def unaryop(self, tree):
        from ast import Invert, Not, UAdd, USub

        unarymap = {
            "~": Invert,
            "not": Not,
            "+": UAdd,
            "-": Usub,
        }
        return unarymap[tree[0].value]

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
        from ast import (
            BoolOp,
            Eq,
            NotEq,
            Lt,
            LtE,
            Gt,
            GtE,
            Is,
            IsNot,
            In,
            NotIn,
            Or,
            And,
            Compare,
        )

        objmap = {
            "==": Eq,
            "!-": NotEq,
            "<": Lt,
            ">": Gt,
            "<=": LtE,
            ">=": GtE,
            "is": Is,
            "is not": IsNot,
            "or": Or,
            "and": And,
        }
        return nt("tokenv value op")(objmap[tree](), Compare)

    def const(self, tree):
        return tree[0]

    def signed_number(self, tree):
        return astlib.const(float(tree[0].value))

    def ifternary(self, tree):
        if len(tree) == 1:
            return tree[0]
        from ast import IfExp

        return IfExp(tree[1], tree[0], tree[2])

    def binopexpr(self, tree):
        from ast import BinOp

        return BinOp(tree[0], tree[1], tree[2])

    def bool(self, tree):
        if tree[0].value == "true":
            return astlib.e("True")
        elif tree[0].value == "false":
            return astlib.e("False")
        else:
            raise ValueError(f"{tree[0]} is not true|false")
