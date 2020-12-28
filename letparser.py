import re
import io
import astlib
from collections.abc import Iterable
from lark import Lark, Transformer as LarkTransformer, Token
from typing import *
from functools import wraps
from collections import namedtuple

from stackdict import StackDict

LetToken = namedtuple("LetToken", "token value")

Buffer = io.BufferedIOBase
Result = Optional[Tuple[Any, Buffer, Callable[[Any, Buffer], Any]]]
RegexResult = tuple[re.Match, Buffer, callable]
Token = tuple[str, str]  # (type, value)

grammar = r"""
    start : let
    ?let : letargs | letdef | letimport | expr
    letargs : "let" (args|kwargs) "in" let
    letdef : "let" "def" ID ID* "in" expr "in" let
    ?letimport : "let" "import" fqalias ("," fqalias)* "in" let | letfromimport
    letfromimport : "let" "from" fqid "import" idalias ("," idalias)* "in" let

    args : arg+
    kwargs : kwarg+
    arg : ID
    kwarg : arg "=" let
    ?expr : doblock | matchexpr | ifternary

    ?doblock : "do" let (";" return )* "end"
    return : "return" let | yield
    yield  : "yield" let | let

    tupleexpr : let "," (let ("," let)*)*

    matchexpr : "let" "match" ID "in" let "=>" let ("|" atom "=>" let)* "end"

    ?ifternary : let "if" boolexpr "else" let | boolexpr

    ?boolexpr : boolexpr BOOL_OP let | binopexpr
    bool : BOOL
    BOOL_OP : "==" | ">=" | ">" | "<" | "<=" | "or" | "and" | "not"
    BOOL : "True" | "False"
    ARROW.10 : "=>"

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
    ?tupleconst : atom "," atom+
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
    res = Transmformator().transform(res)
    return res


class Transmformator(LarkTransformer):
    def start(self, tree):
        from ast import Module, expr, Expr

        stmts = [Expr(s) if isinstance(s, expr) else s for s in self.statements]
        res = Module(body=stmts, type_ignores=[])
        return res

    def kwargs(self, tree):
        return {t.children[0].children[0].id: t.children[1] for t in tree}

    def args(self, tree):
        return [t.children[0].id for t in tree]

    def let(self, tree):
        e = tree[1][0] if isinstance(tree[1], list) and len(tree[1]) >= 1 else tree[1]
        if isinstance(tree[0], dict):
            return astlib.let(**tree[0])(e)
        return astlib.letargs(*tree[0])(e)

    def body_helper(self, body):
        from ast import expr, Return

        # place return in the last expression of body
        if isinstance(body, expr):
            body = [Return(body)]
        elif isinstance(body, list) and not isinstance(body[-1], Return):
            body[-1] = Return(body[-1])

        return body

    def __init__(self):
        self.statements = []

    def letdef(self, tree):
        from ast import FunctionDef, arg, Lambda, arguments

        name, *args, body, cont = tree
        body = self.body_helper(body)
        fdef = FunctionDef(
            name=name.id,
            args=arguments(
                posonlyargs=[],
                args=[arg(a.id) for a in args],
                vararg=arg("args"),
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=arg("kwargs"),
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
            type_commends=[],
        )
        self.statements.append(fdef)
        self.statements.append(cont)
        return name

    def integer(self, tree):
        from ast import Constant

        return Constant(int(tree[0]))

    def ID(self, tree):
        if hasattr(tree, "value") and tree.value in ("true", "false"):
            from ast import Constant

            return Constant("true" == tree.value)

        return astlib.name(tree.value)

    def fqid(self, tree):
        from ast import Attribute, Load
        from functools import reduce

        if len(tree) == 1:
            return tree[0]
        call = Attribute(tree[0], tree[1], ct=Load())
        res = reduce(
            lambda a, b: Attribute(a, b.id, ctx=Load()),
            tree,
        )
        return res

    def MATH_PLUS(self, tree):
        from ast import Add, Sub, Mult, Div, FloorDiv, Mod, Pow

        token = tree[0]
        opmap = {
            r"+": Add,
            r"-": Sub,
            r"*": Mult,
            r"/": Div,
            r"//": FloorDiv,
            r"%": Mod,
            r"**": Pow,
        }

        return opmap[token]()

    MATH_MUL = MATH_PLUS
    MATH_PW = MATH_PLUS
    MATH_UNARY = MATH_PLUS

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

    def tupleconst(self, tree):
        return tree

    def callargs(self, tree):
        if isinstance(tree[0], list):
            return tree[0]
        return tree

    def call(self, tree):
        from ast import Call

        res = Call(tree[0], args=tree[1], keywords=[])
        return res

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
