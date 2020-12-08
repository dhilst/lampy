from lark import Lark, Tree
from lark.visitors import Transformer as LarkTransformer

from lampy.tlampy import Var, Val, Appl, Lamb, BinOp, AST, TypeUnk, TypeVar, TypeArrow

grammar = r"""
    module: stmt+
    stmt : term+ ";"

    ?term : lamb
    ?lamb : "(" _args ") =>" term | bin_expr
    _args : tvar | _args "," tvar

    ?bin_expr : bin_expr plusop numfactor
              | numfactor
    ?numfactor: numfactor mulop appl
              | appl

    ?appl : appl atom | atom

    ?atom: "(" term ")"
        | ID -> var
        | SIGNED_INT -> intval
        | ESCAPED_STRING -> strval

    tvar: ID ":" typespec
    ?typespec : type "->" typespec | type
    !type : "int" | "str" | typevar
    typevar : "'" ID | tpar
    tpar : "(" typespec ")"

    ID : /[a-z]/
    !?mulop : "*" | "/"
    !?plusop: "+" | "-"

    %import common.WS
    %import common.SH_COMMENT
    %import common.ESCAPED_STRING
    %import common.SIGNED_INT
    %ignore WS
    %ignore SH_COMMENT

"""

lamb_parser = Lark(grammar, start="module", parser="lalr")


def _str_to_builtins(s: str):
    return __builtins__[s]  # type: ignore


class Transformer(LarkTransformer):
    def lamb(self, tree):
        *args, lastarg, body = tree
        lamb = Lamb(lastarg, body)
        # fold lambdas
        for arg in reversed(args):
            lamb = Lamb(arg, lamb)
        return lamb

    def var(self, tree):
        return Var(tree[0].value, TypeUnk())

    def bin_expr(self, tree):
        a, op, b = tree
        return BinOp(op, a, b)

    def appl(self, tree):
        e1, e2 = tree
        return Appl(e1, e2)

    def type(self, tree):
        if isinstance(tree[0], str):
            return _str_to_builtins(tree[0])
        return tree[0]

    def tvar(self, tree):
        return Var(tree[0], tree[1])

    def intval(self, tree):
        return Val(tree[0], int)

    def strval(self, tree):
        return Val(tree[0], str)

    def stmt(self, tree):
        return AST(tree[0])

    def typespec(self, tree):
        return TypeArrow(tree[0], tree[1])

    def typevar(self, tree):
        # typevar may be called after typespec
        # in this case just return
        if isinstance(tree[0], TypeArrow):
            return tree[0]
        return TypeVar(tree[0].value)

    def tpar(self, tree):
        return self.type(tree)


def parse(input_, typecheck=True):
    res = Transformer().transform(lamb_parser.parse(input_)).children
    for c in res:
        if typecheck:
            c.typecheck()
    return res
