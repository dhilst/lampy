from lark import Lark, Tree
from lark.visitors import Transformer as LarkTransformer

from lampy.lampy import Var, Val, Appl, Lamb, BinOp, AST

grammar = r"""
    module: stmt+
    stmt : term+ ";"

    ?term : lamb
    ?lamb : "(" args ") =>" term | bin_expr
    ?args : ID | args "," ID

    ?bin_expr : bin_expr plusop numfactor
              | numfactor
    ?numfactor: numfactor mulop appl
              | appl

    ?appl : appl atom | atom

    ?atom: "(" term ")"
        | ID -> var
        | SIGNED_NUMBER -> val

    ID : /[a-z]/
    SIGNED_NUMBER: /(\+|-)?\d+(\.\d+)?/
    !?mulop : "*" | "/"
    !?plusop: "+" | "-"

    %import common.WS
    %import common.SH_COMMENT
    %ignore WS
    %ignore SH_COMMENT

"""

lamb_parser = Lark(grammar, start="module", parser="lalr")


class Transformer(LarkTransformer):
    def lamb(self, tree):
        args, body = tree
        if not isinstance(args, Tree):
            # args is a single argument
            return Lamb(Var(args), body)
        *args, lastarg = [t.value for t in args.children]
        lamb = Lamb(Var(lastarg), body)
        # fold lambdas
        for arg in reversed(args):
            lamb = Lamb(Var(arg), lamb)
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
