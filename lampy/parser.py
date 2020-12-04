from sly import Lexer, Parser as SlyParser

from .lampy import Var, Val, Lamb, Appl, AST


class Lex(Lexer):
    """
    >>> list(Lex().tokenize("fn x => x"))
    [Token(type='FN', value='fn', lineno=1, index=0), Token(type='ID', value='x', lineno=1, index=3), Token(type='DARROW', value='=>', lineno=1, index=5), Token(type='ID', value='x', lineno=1, index=8)]
    """

    tokens = {ID, NUMBER, FN, PLUS, MINUS, TIMES, DIVIDE, LPAR, RPAR, DARROW}

    ignore = "\t\n "

    ID = r"[w-z]"
    NUMBER = r"\d+"
    PLUS = r"\+"
    MINUS = r"-"
    TIMES = r"\*"
    DIVIDE = r"/"
    LPAR = r"\("
    RPAR = r"\)"
    FN = r"fn"
    DARROW = r"=>"


class Parser(SlyParser):
    """
    term : appl | abst | var
    var  : ID | NUMBER | "(" term ")"
    appl : appl term
    asbt : fn ID => term

    >>> parse("fn x => fn y => x").eval()
    (λx.(λy.x))

    >>> parse("(fn x => fn y => x) 1 2").eval()
    1
    """

    debugfile = "parser.out"

    tokens = Lex.tokens

    @_("appl", "lamb", "var")
    def term(self, p):
        return p[0]

    @_("ID")
    def var(self, p):
        return Var(p.ID)

    @_("NUMBER")
    def var(self, p):
        return Val(p.NUMBER)

    @_("LPAR term RPAR")
    def var(self, p):
        return p.term

    @_("term var")
    def appl(self, p):
        """
        >>> parse("x x").eval()
        x x
        """
        return Appl(p.term, p.var)

    @_("FN ID DARROW term")
    def lamb(self, p):
        """
        >>> parse("fn x => x").eval()
        (λx.x)
        """
        return Lamb(Var(p.ID), p.term)


def parse(input: str):
    return AST(Parser().parse(Lex().tokenize(input)))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
