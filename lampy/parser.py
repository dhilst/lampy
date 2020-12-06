from lark import Lark
from lark.visitors import Transformer as LarkTransformer

from lampy.lampy import Var, Val, Appl, Lamb, BinOp, AST

grammar = r"""
    module: stmt+
    stmt : term+ ";"

    ?term : lamb
    ?lamb : ID+ "=>" term | bin_expr

    ?bin_expr : bin_expr plusop numfactor
             | numfactor
    ?numfactor: numfactor mulop appl
             | appl

    ?appl : appl val | val

    ?val : "(" term ")"
         | ID -> var
         | SIGNED_NUMBER -> val

    ID : /[a-z]/
    !?mulop : "*" | "/"
    !?plusop: "+" | "-"

    %import common.SIGNED_NUMBER
    %import common.WS
    %import common.SH_COMMENT
    %ignore WS
    %ignore SH_COMMENT
"""

lamb_parser = Lark(grammar, start="module")


class Transformer(LarkTransformer):
    def lamb(self, tree):
        *args, lastarg, body = tree
        lamb = Lamb(Var(lastarg.value), body)
        # fold lambdas
        for arg in reversed(args):
            lamb = Lamb(Var(arg.value), lamb)
        return lamb

    def bin_expr(self, tree):
        a, op, b = tree
        return BinOp(op, a, b)

    def appl(self, tree):
        e1, e2 = tree
        return Appl(e1, e2)

    def var(self, tree):
        return Var(tree[0])

    def val(self, tree):
        return Val(float(tree[0]))

    def stmt(self, tree):
        return AST(tree[0])


def parse(input_):
    return Transformer().transform(lamb_parser.parse(input_)).children
