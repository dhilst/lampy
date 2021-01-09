import re
import io
import astlib
from collections.abc import Iterable
from lark import Lark, Transformer as LarkTransformer, Token
from typing import *
from functools import wraps
from collections import namedtuple

from stackdict import StackDict

from astlib import get, attrs

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
    letfromimport : "let" "from" relativeid "import" idalias ("," idalias)* "in" let

    args : arg+
    kwargs : kwarg+
    arg : ID
    kwarg : arg "=" let
    ?expr : doblock | matchexpr | ifternary

    ?doblock : "do" let (";" return )* "end"
    return : "return" let | yield
    yield  : "yield" let | let

    matchexpr : "match" atom "with" ("|" pattern)+ "end"
    pattern:  pattern_left ARROW let
    !pattern_left : EMPTY | const | ID ("," "*"? ID)* | fqid "(" (arg|kwarg)* ")"
    unpack: "*" ID

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


    ?call: atom callargs+ | subscript
    ?subscript : atom "[" let "]" | atom
    callargs : "(" (let ("," let)* )* ")"

    ?atom: "(" let ")" | const | fqid

    const : bool | integer | dictconst | listconst | tupleconst | setconst | NONE | STRING_CONST
    dictconst : "{" atom ":" atom ("," atom ":" atom )* "}"
    listconst : "[" let ("," let)* "]"
    tupleconst : "(" let "," (let | ("," let))* ")"
    setconst : "{" let ("," let)* "}"
    integer : /[+-]?\d+/ | /0x[a-fA-F]+/ | /0o[0-7]+/ | /0b[12]+/ | float
    float : /[+-]?\d+\.\d+/

    NONE.10 : "None"
    STRING_CONST.5: STRING_MODIFIER? ESCAPED_STRING

    fqalias : fqid ("as" ID)?
    !relativeid : "."+ fqalias
    idalias : ID ("as" ID)?
    fqid : ID ("." ID)*
    ID : CNAME
    STRING_MODIFIER.10 :  "f" | "r" | "b"
    EMPTY.11 : "[]"
    LBRAKET.5 : "["
    RBRAKET.5 : "]"
    LBRACE.5 : "{"
    RBRACE.5 : "}"
    LPAR.4 : "("
    RPAR.4 : ")"



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
    import os
    res = let_parser.parse(input_)
    res = Transmformator().transform(res)

    if "DUMP_AST" in os.environ:
        res.dump()
    return res


class Transmformator(LarkTransformer):
    def subscript(self, tree):
        from ast import Subscript, Load
        return Subscript(tree[0], tree[1], Load())

    def relativeid(self, tree):
        from ast import alias
        from lark import Token

        res = []
        for t in tree:
            if isinstance(t, Token):
                res.append(t.value)
            elif isinstance(t, alias):
                res.append(t.name)
            else:
                raise TypeError(f"invalid tree type {tree}")
        return "".join(res)

    def start(self, tree):
        from ast import Module, expr, Expr
        stmts = [
            Expr(s) if isinstance(s, expr) else s for s in reversed(self.statements)
        ]
        stmts.append(Expr(tree[0]))
        res = Module(body=stmts, type_ignores=[])
        return res

    def letimport(self, tree):
        from ast import Import, alias, expr, Expr

        *imps, cont = tree[0:-1], tree[-1]
        imps = imps[0]
        imp = Import(names=imps)
        self.statements.append(cont)
        self.statements.append(imp)
        return imp

    def letargs(self, tree):
        return let(tree[0])(tree[1])

    def matchexpr(self, tree):
        from ast import Name, Call, Load, Tuple
        import astlib

        name, patterns = tree[0], tree[1:]
        __import__('pdb').set_trace()
        patterns = [Tuple(elts=[astlib.lazy(repr(p[0]) if not isinstance(p[0], str) else p[0]), p[1]], ctx=Load()) for p in patterns]
        res = Call(Name("match", Load()), [name] + patterns, [])
        return res

    def pattern(self, tree):
        return (tree[0], astlib.lamb()(tree[2]))

    def pattern_left(self, tree):
        from ast import Name, Constant
        if tree[0] << get("type") == "EMPTY":
            return "[]"
        elif isinstance(tree[0], (Name, Constant)):
            return "".join(str(attrs(t, "value", "id")) for t in tree)
        elif tree[0] << get("data") == "fqid":
            print("is an arg")
            args = []
            for a in tree[0]:
                if a << get("data") == "arg":
                    args.append(a.children[0].id)
                elif a << get("data") == "kwarg":
                    args.append(f"{k}={v}" for k, v in a.items())
            args = ", ".join(args)
            return tree[0].unparse() + "(" + args + ")"
        else:
            raise ValueError


    def letfromimport(self, tree):
        from ast import ImportFrom, alias, Attribute
        from lark import Tree

        def flat_attrs(attr):
            if isinstance(attr, str):
                return attr
            elif isinstance(attr, Attribute):
                name = flat_attrs(attr.value)
            elif hasattr(attr, "value"):
                name = attr.value.id
            return ".".join((name, attr.attr))

        def count_dots(fqmod):
            count = 0
            for char in fqmod:
                if char == ".":
                    count += 1
                else:
                    break
            return count

        is_idalias = isinstance(tree[0], Tree) and tree[0].data == "idalias"
        modfqname = flat_attrs(tree[0]) if not is_idalias else tree[0].children[0].id
        aliases = [
            alias(a.children[0].id, a.children[1].id)
            if len(a.children) == 2
            else alias(a.children[0].id)
            for a in tree[1:-1]
        ]
        cont = tree[-1]
        level = count_dots(modfqname)
        fimp = ImportFrom(module=modfqname, names=aliases, level=level)
        self.statements.append(cont)
        self.statements.append(fimp)
        return fimp

    def kwargs(self, tree):
        return {t.children[0].children[0].id: t.children[1] for t in tree}

    def args(self, tree):
        return [t.children[0].id for t in tree]

    def letargs(self, tree):
        e = tree[1][0] if isinstance(tree[1], list) and len(tree[1]) >= 1 else tree[1]
        if isinstance(tree[0], dict):
            return astlib.let(**tree[0])(e)
        return astlib.letargs(*tree[0])(e)

    def fqalias(self, tree):
        from ast import alias

        name, *_alias = tree
        if _alias:
            return alias(name.id, _alias[0].id)
        return alias(name.id)

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
        self.statements.append(cont)
        self.statements.append(fdef)
        return cont

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
        if len(tree) == 1 and isinstance(tree[0], list):
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

    def NONE(self, token):
        return astlib.lazy("None")

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

    def listconst(self, tree):
        from ast import List,Load
        return List(elts=tree, ctx=Load())

    def tupleconst(self, tree):
        from ast import Tuple ,Load
        return Tuple(elts=tree, ctx=Load())

    def dictconst(self, tree):
        from ast import Dict,Load
        keys = tree[0::2]
        values = tree[1::2]
        return Dict(keys, values)

    def STRING_CONST(self, tree):
        from ast import Constant
        return Constant("".join(c for c in tree.value if c not in ("'", '"')))
