import os
import sys
from abc import ABC, abstractmethod
from typing import (
    Dict,
    Any,
    NamedTuple,
    Optional,
    Callable,
    TypedDict,
    Generic,
    TypeVar,
    Iterable,
    Sequence,
    Tuple,
    Union,
)
from pyparsing import (  # type: ignore
    Combine,
    Empty,
    Forward,
    Group,
    Keyword,
    LineEnd,
    Literal,
    NoMatch,
    ParserElement,
    ParseResults,
    Word,
    alphanums,
    alphas,
    nums,
    dblQuotedString,
    delimitedList,
    infixNotation,
    nums,
    oneOf,
    opAssoc,
    restOfLine,
    ungroup,
)
import operator as op
from collections import namedtuple
from functools import reduce
from pprint import pprint


_bound_vars = set()


def _next_var(v: "Var") -> "Var":
    """
    Return the next letter

    >>> _next_var(Var("u"))
    v

    >>> _next_var(Var("z"))
    u
    """
    global _bound_vars
    first = ord("u")
    last = ord("z")
    index = ord(v.name)
    while True:
        next_ = ord(v.name) + 1
        if next_ > last:
            next_ = first
        found = Var(chr(next_))
        if found not in _bound_vars:
            return Var(chr(next_))


def _reset_bound_vars():
    global _bound_vars
    _bound_vars = set()


def _bind(var: "Var"):
    _bound_vars.add(var.name)


class Term(ABC):
    @abstractmethod
    def replace(self, old, new) -> "Term":
        pass

    @property
    def is_norm(self) -> bool:
        """
        Is in beta-normal form?

        >>> Lamb(Var("x"), Var("x")).is_norm
        True
        >>> Var("x").is_norm
        True
        >>> Val("1").is_norm
        True
        >>> Appl(Lamb(Var("x"), Var("x")), Val("1")).is_norm
        False
        """
        if isinstance(self, Appl):
            if isinstance(self.e1, Lamb):
                return False
            else:
                return self.e1.is_norm and self.e2.is_norm
        elif isinstance(self, BinOp):
            return False
        return True


class BinOp(Term):
    """
    >>> eval_term(BinOp("+", Val("1"), Val("1")))
    2

    >>> AST(Appl(Lamb(Var("x"), BinOp("+", Var("x"), Val("1"))), Val("2"))).eval()
    3
    """

    opmap = {
            '+': op.add,
            '*': op.mul,
            '/': op.truediv,
            '-': op.sub,
    }

    def __init__(self, op: str, a: Term, b: Term):
        self.a = a
        self.op = op
        self.b = b
        if op not in self.__class__.opmap:
            raise TypeError(f"Unknown operator {op}")

    @property
    def opfun(self):
        return self.__class__.opmap[self.op]

    def replace(self, old, new):
        self.a = self.a.replace(old, new)
        self.b = self.b.replace(old, new)
        return self

    def __repr__(self):
        return f"{self.a} {self.op} {self.b}"


class Var(Term):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

    def replace(self, old, new) -> "Term":
        if self.name == old.name:
            return new
        return self


class Val(Term):
    def __init__(self, val):
        self.val = int(val)

    def __repr__(self):
        return str(self.val)

    def replace(self, old, new) -> "Term":
        return self


class Lamb(Term):
    body: Term

    def __init__(self, var: Var, body: Term):
        self.var = var
        self.body = body
        _bind(self.var)

    def replace(self, old: Var, new: Term) -> "Term":
        if isinstance(new, Var) and new.name == self.var.name:
            # alpha conversion
            old_var = self.var
            self.var = _next_var(self.var)
            self.body = self.body.replace(old_var, self.var)
        self.body = self.body.replace(old, new)
        return self

    def __repr__(self):
        return f"(λ{self.var}.{self.body})"


class Appl(Term):
    def __init__(self, e1, e2):
        self.e1 = e1
        self.e2 = e2

    def replace(self, old, new):
        self.e1 = self.e1.replace(old, new)
        self.e2 = self.e2.replace(old, new)
        return self

    def __repr__(self):
        if isinstance(self.e2, Appl):
            return f"{self.e1} ({self.e2})"
        return f"{self.e1} {self.e2}"


def appl(lam: "Lamb", term: Term, i = 0):
    """
    >>> appl(Lamb(Var("x"), Var("x")), Val("1"))
    1
    >>> appl(Lamb(Var("x"), Lamb( Var("y"), Appl(Var("x"), Var("y")) )), Val("1"))
    (λy.1 y)

    >>> appl(Lamb(Var("x"), Lamb( Var("y"), Appl(Var("x"), Var("y")) )), Var("y"))
    (λz.y z)

    >>> appl(Lamb(Var("x"), Var("x")), Lamb(Var("y"), Var("y")))
    (λy.y)
    """
    res = lam.replace(lam.var, term)
    if isinstance(res, Lamb):
        print(f"{'  ' * i}appl({lam}, {term}) => {res.body}", file=sys.stderr)
        return res.body

    raise TypeError(f"{res} is not a lambda")


def eval_term(term: Term, i = 0) -> Term:
    """
    Abstration evaluate to it self
    >>> eval_term(Lamb(Var("x"), Var("x")))
    (λx.x)

    Value evaluate to it self
    >>> eval_term(Appl(Lamb(Var("x"), Var("x")), Val("1")))
    1

    Application evalute by CBV
    >>> eval_term(Appl(Lamb(Var("x"), Var("x")), Lamb(Var("y"), Var("y"))))
    (λy.y)
    """
    print(f"{'  ' * i}eval({term})", file=sys.stderr)
    if isinstance(term, Appl):
        e1 = eval_term(term.e1, i+1)
        e2 = eval_term(term.e2, i+1)
        if isinstance(e1, Lamb):
            return appl(e1, e2, i+1)
    elif isinstance(term, BinOp):
        a = eval_term(term.a, i+1)
        b = eval_term(term.b, i+1)
        if isinstance(a, Val) and isinstance(b, Val):
            return Val(term.opfun(a.val, b.val))

    return term


class AST:
    def __init__(self, root: Term):
        self.root = root

    def eval(self):
        """
        I
        >>> parse("(fn x => x) 1").eval()
        1

        K combinator
        >>> parse("(fn x => fn y => x) 1 2").eval()
        1

        S combinator
        >>> parse("(fn x => fn y => fn z => x z (y z)) (fn x => fn y => x) (fn x => x) 1").eval()
        1
        """
        _reset_bound_vars()
        t = eval_term(self.root)
        while not t.is_norm:
            t = eval_term(t)
        print("", file=sys.stderr)
        return t


def BNF() -> ParserElement:
    """
    Our grammar
    """
    if hasattr(BNF, "cache"):
        return BNF.cache  # type: ignore

    def to_lambda(t):
        return Lamb(Var(t.arg), t.body.asList()[0])

    def to_application(t):
        # Left associativity
        return reduce(Appl, t)

    def to_variable(t) -> Var:
        return Var(t[0])

    def to_val(t) -> Val:
        return Val(t[0])

    def to_bin(t) -> BinOp:
        return BinOp(t[0][1], t[0][0], t[0][2])

    ID = Word(alphas, exact=1)
    VAL = Word(nums)
    FN = Literal("fn").suppress()
    ARROW = Literal("=>").suppress()
    LP = Literal("(").suppress()
    RP = Literal(")").suppress()

    comment = Literal("#").suppress() + restOfLine

    term = Forward()
    appl_ = Forward()

    # abst ::= "fn" ID "=>" term+
    abst = FN + ID("arg") + ARROW + term[1, ...]("body")

    var = ID | VAL | LP + term + RP

    # Binary expression
    binexpr = infixNotation(
        var,
        (
            (oneOf("* /"), 2, opAssoc.LEFT),
            (oneOf("+ -"), 2, opAssoc.LEFT),
        )
    )


    appl_ <<= var + appl_[...]  # applseq("e2")
    appl = appl_ | NoMatch()  # add no match to create a new rule

    term <<= abst | appl | var 

    term.ignore(comment)
    ID.setParseAction(to_variable)
    VAL.setParseAction(to_val)
    binexpr.setParseAction(to_bin)
    abst.setParseAction(to_lambda)
    appl.setParseAction(to_application)

    term.validate()

    BNF.cache = term  # type: ignore

    return term


def parse(input: str) -> AST:
    return AST(BNF().parseString(input, True)[0])


if __name__ == "__main__":
    BNF().runTests(
        """
       # Simple abstraction
       fn x => x y y

       # Chainned abstrxction
       fn x => fn y => x y

       # Abstraction application
       (fn x => x y) (fn x => x)

       # Try left associativity of appliction
       u v w x y z

       # Simple xpplicxtion
       (fn x => x) a

       # ɑ conversion needed
       (fn x => x y) a

       # Value
       1

       # Parenthesis
       x z (y z)
       """
    )
