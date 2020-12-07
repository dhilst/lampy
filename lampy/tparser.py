from lark import Lark, Tree
from lark.visitors import Transformer as LarkTransformer

from lampy.tlampy import Var, Val, Appl, Lamb, BinOp, AST, TypeUnk

grammar = r"""
    module: stmt+
    stmt : term+ ";"

    ?term : lamb
    ?lamb : "(" args ") =>" term | bin_expr
    ?args : tvar | args "," ID

    ?bin_expr : bin_expr plusop numfactor
              | numfactor
    ?numfactor: numfactor mulop appl
              | appl

    ?appl : appl atom | atom

    ?atom: "(" term ")"
        | ID -> var
        | SIGNED_INT -> intval
        | ESCAPED_STRING -> strval

    tvar: | ID ":" type
    type : "int" -> int | "str" -> str

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


class Transformer(LarkTransformer):
    def lamb(self, tree):
        args, body = tree
        if isinstance(args, Var):
            # args is a single argument
            return Lamb(args, body)
        *args, lastarg = [t.value for t in args.children]
        lamb = Lamb(Var(lastarg), body)
        # fold lambdas
        for arg in reversed(args):
            lamb = Lamb(Var(arg), lamb)
        return lamb

    def var(self, tree):
        return Var(tree[0].value, TypeUnk)

    def bin_expr(self, tree):
        a, op, b = tree
        return BinOp(op, a, b)

    def appl(self, tree):
        e1, e2 = tree
        return Appl(e1, e2)

    def tvar(self, tree):
        return Var(tree[0], tree[1])

    def intval(self, tree):
        return Val(tree[0], int)

    def strval(self, tree):
        return Val(tree[0], str)

    def stmt(self, tree):
        return AST(tree[0])


def parse(input_):
    return Transformer().transform(lamb_parser.parse(input_)).children
