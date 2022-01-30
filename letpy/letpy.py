from math import inf
import re
import enum
from dataclasses import dataclass
from typing import *
import ast
from io import StringIO
import functools
import operator


def _flat(it):
    for i in it:
        try:
            if isinstance(i, (str, tuple)):
                yield i
            elif i is None:
                pass
            else:
                yield from i
        except TypeError:
            yield i


def flat(it):
    return list(_flat(it))


def test_flat():
    x = flat([1, [2, 3], None, 4, 5])
    assert x == [1, 2, 3, 4, 5]


class Eq:
    def __eq__(self, other):
        return self.__class__ == other.__class__ and all(
            self.__dict__[k] == other.__dict__[k] for k in self.__dict__.keys()
        )


class Result(Eq):
    input: "Input"
    pos: int
    value: Any

    def __repr__(self):
        return f"{self.__class__.__name__}({self.__dict__})"


class Ok(Result):
    def __init__(self, v, input):
        self.value = v
        self.input = input


class Err(Result):
    def __init__(self, error, input):
        self.error = error
        self.input = input


class Input:
    def __init__(self, input: str, pos=0):
        self.input = input
        self._pos = pos

    @property
    def pos(self):
        return self._pos

    def __repr__(self):
        return f"Input({self.input[self.pos:10]}, {self.pos})"

    def get(self, length):
        return self.input[self.pos : self.pos + length]

    def getall(self) -> str:
        return self.input[self.pos :]

    def clone(self, posinc):
        return Input(self.input, self.pos + posinc)

    def skip_spaces(self):
        pos = self.pos
        for ch in self.getall():
            if ch.isspace():
                pos += 1
            else:
                return Input(self.input, pos)
        return Input("", pos)

    def __eq__(self, other):
        return self.pos == other.pos and self.input == other.input


class Parser:
    def _normalize(self, other):
        if isinstance(other, str):
            return Regex(other)
        return other

    def __and__(self, other):
        other = self._normalize(other)
        return And(self, other)

    def __or__(self, other):
        other = self._normalize(other)
        return Or(self, other)

    def __mul__(self, other):
        return Many(self, other)

    def __gt__(self, other):
        return Hook(self, other)

    def __invert__(self):
        return Ignore(self)

    def run(self, input: Input) -> Result:
        pass


class Hook(Parser):
    def __init__(self, parser, hook):
        self.parser = parser
        self.hook = hook

    def run(self, input):
        res = self.parser.run(input)
        if isinstance(res, Ok):
            if isinstance(res.value, str):
                return Ok(self.hook(res.value), res.input)
            else:
                return Ok(self.hook(*res.value), res.input)
        else:
            return res


class And(Parser):
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

    def run(self, input: Input):
        r1 = self.p1.run(input)
        if isinstance(r1, Err):
            return r1

        r2 = self.p2.run(r1.input)
        if isinstance(r2, Err):
            return Err(r2.error, input)

        return Ok(flat([r1.value, r2.value]), r2.input)


class Or(Parser):
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

    def run(self, input: Input):
        r1 = self.p1.run(input)
        if isinstance(r1, Ok):
            return r1
        else:
            return self.p2.run(input)


class Regex(Parser):
    def __init__(self, pattern):
        self.pattern = re.compile(pattern)

    def run(self, input):
        input = input.skip_spaces()
        match = self.pattern.match(input.getall())
        if match is not None:
            return Ok(match.group(0), input.clone(match.end(0)))
        else:
            return Err(f"Expect regex {self.pattern} found {input.getall()}", input)


class Lit(Parser):
    def __init__(self, pattern):
        self.parser = Ignore(Regex(pattern))

    def run(self, input):
        return self.parser.run(input)


# One or more
class Many(Parser):
    def __init__(self, parser: Parser, n=inf):
        self.parser = parser
        self.n = n

    def run(self, input: Input):
        results: List[str] = []
        pos = input.pos

        result = self.parser.run(input)
        if isinstance(result, Ok):
            results.append(result.value)
            input = result.input
        else:
            return result

        i = 0
        while i < self.n:
            result = self.parser.run(input)
            if isinstance(result, Ok):
                results.append(result.value)
                input = result.input
                i += 1
            else:
                return Ok(results, input)


class Ignore(Parser):
    def __init__(self, parser):
        self.parser = parser

    def run(self, input):
        pos = input.pos
        r = self.parser.run(input)
        if isinstance(r, Ok):
            return Ok(None, r.input)
        return r


_keywords = set()


class Keyword(Parser):
    def __init__(self, keyword):
        _keywords.add(keyword)
        self.parser = ~Regex(keyword)

    def run(self, input):
        return self.parser.run(input)


class NotKeyword(Parser):
    def __init__(self, parser):
        self.parser = parser

    def run(self, input):
        for k in _keywords:
            r = Regex(k).run(input)
            if isinstance(r, Ok):
                return Err(f"Unexpected keyword {k}", input)

        return self.parser.run(input)


class Group(Parser):
    def __init__(self, parser):
        self.parser = parser

    def run(self, input):
        res = self.parser.run(input)
        if isinstance(res, Ok):
            return Ok(tuple(flat(res.value)), res.input)
        else:
            return res


class Left(Parser):
    """Infix left associativite parser combinator

    Accepts two parsers, a term and a operator, for example

    >>> Left(Regex(r"\w"), Regex(r"\+")).run(Input("a + b + c + d")).value
    [[['a', '+', 'b'], '+', 'c'], '+', 'd']
    """

    @dataclass
    class Phrase:
        term: str
        op: Optional[str]

    @dataclass
    class Term:
        term: str

    def __init__(self, term, op):
        self.term = term
        self.op = op

    def _run(self, input, prev=None):
        res = ((self.term & self.op > Left.Phrase) | (self.term > Left.Term)).run(input)
        if isinstance(res, Err):
            return prev if prev is not None else res
        if isinstance(res.value, Left.Term):
            # end of parsable input stream
            if prev is not None:
                return Ok([*prev.value, res.value.term], res.input)
            else:
                return Ok(res.value.term, res.input)
        elif isinstance(res.value, Left.Phrase):
            val = [res.value.term, res.value.op]
            if prev is None:
                return self._run(res.input, Ok(val, res.input))
            else:
                val = [[*prev.value, val[0]], *val[1]]
                return self._run(res.input, Ok(val, res.input))
        else:
            raise RuntimeError("BUG")

    def run(self, input):
        return self._run(input)


class LeftEmpty(Parser):
    def __init__(self, term):
        self.term = term

    # foo bar tar zar
    # Ok({'value': [Ok({'value': [['foo', 'bar'], 'tar'], 'input': Input(, 11)}), 'zar'], 'input': Input(, 15)})
    def _run(self, input, acc=None):
        if acc is None:
            res = (self.term & self.term).run(input)
            if isinstance(res, Err):
                return self.term.run(input)

            return self._run(res.input, res.value)
        else:
            res = self.term.run(input)
            if isinstance(res, Err):
                return Ok(acc, input)
            else:
                return self._run(res.input, [acc, res.value])

    def run(self, input):
        return self._run(input)


# Terminals
LET = Keyword("let")  # Literal, parse result is ignored
FUN = Keyword("fun")
FAT_ARROW = Keyword("=>")
ARROW = Keyword("->")
EQUAL = Lit("=")
IN = Keyword("in")
LPAR = Lit(r"\(")
RPAR = Lit(r"\)")
word = NotKeyword(Regex(r"\w+"))
words = word * inf  # zero or more


class Expr(Parser):
    def run(self, input: Input):
        return (ParExpr() | Fun() | LetAssign() | Appl() | word).run(input)


class ParExpr(Parser):
    def run(self, input):
        return (LPAR & Expr() & RPAR > AST.ParExpr).run(input)


class Fun(Parser):
    def run(self, input):
        return ((FUN & word & FAT_ARROW & Expr()) > AST.Fun).run(input)


class LetAssign(Parser):
    def run(self, input):
        print("letlamb input", input)
        return ((LET & word & EQUAL & Expr() & IN & Expr()) > AST.LetAssign).run(input)


class Appl(Parser):
    def run(self, input):
        # This is wrooong
        return ((word & Expr() | word) > AST.Appl).run(input)


class AST:
    @dataclass
    class Fun:
        parm: str
        body: Expr

    @dataclass
    class LetAssign:
        parm: str
        arg: Expr
        body: Expr

    @dataclass
    class ParExpr:
        expr: Expr

    @dataclass
    class Appl:
        args: List[Expr]
        fun: Expr


def _test_fail_preserves_input(input, parser):
    i = Input(input)
    r = parser.run(i)
    assert isinstance(r, Err) and i == r.input


def _test_success(input, parser, output):
    i = Input(input)
    r = parser.run(i)
    assert isinstance(r, Ok) and r.value == output


def test_input():
    assert Input("   foo").skip_spaces().getall() == "foo"
    assert Input("foo").skip_spaces().getall() == "foo"
    assert Input("").skip_spaces().getall() == ""


def test_combinators():
    # Failure preseves input
    i = "foo bar tar zar"
    _test_fail_preserves_input(i, Regex("blabla"))
    _test_fail_preserves_input(i, Regex("foo") & Regex("banana"))
    _test_fail_preserves_input(i, Regex("banana") & Regex("foo"))
    _test_fail_preserves_input(i, Regex("banana") | Regex("avocado"))
    _test_fail_preserves_input(i, Many(Regex(r"\d")))
    _test_fail_preserves_input(i, Ignore(Regex(r"\d")))
    _test_fail_preserves_input(i, Regex("foo") & "bar" & "tar" & "zar" & "banana")
    _test_fail_preserves_input(
        i, Regex("foo") & "bar" & "tar" & (Lit("café") | "banana")
    )
    _test_fail_preserves_input(i, (Regex("foo") | "bar") & "banana")

    _test_success(i, Regex("foo") & "bar" & "tar" & "zar", ["foo", "bar", "tar", "zar"])
    _test_success(i, LeftEmpty(Regex(r"\w+")), [[["foo", "bar"], "tar"], "zar"])


def test_lang():
    _test_success("fun foo => bar", Expr(), AST.Fun(parm="foo", body="bar"))
    _test_success(
        "let foo = bar in foo",
        LetAssign(),
        AST.LetAssign(parm="foo", arg="bar", body="foo"),
    )

    _test_success(
        "let foo = (fun bar => tar) in foo",
        Expr(),
        AST.LetAssign(
            parm="foo",
            arg=AST.ParExpr(AST.Fun(parm="bar", body="tar")),
            body="foo",
        ),
    )

    _test_success(
        "let foo = bar in let tar = zar in bla",
        Expr(),
        AST.LetAssign(
            parm="foo", arg="bar", body=AST.LetAssign(parm="tar", arg="zar", body="bla")
        ),
    )

    _test_success(
        "let f = fun x => x in f",
        Expr(),
        AST.LetAssign(parm="f", arg=AST.Fun(parm="x", body="x"), body="f"),
    )

    # Function application is reversed
    # and curried
    _test_success(
        "a b c d e func",
        Expr(),
        AST.Appl(
            args="a",
            fun=AST.Appl(
                args="b",
                fun=AST.Appl(
                    args="c", fun=AST.Appl(args="d", fun=AST.Appl(args="e", fun="func"))
                ),
            ),
        ),
    )
