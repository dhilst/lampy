import re
import io
import astlib
from lark import Lark, Transformer as LarkTransformer, Token
from typing import *
from functools import wraps

Buffer = io.BufferedIOBase
Result = Optional[Tuple[Any, Buffer, Callable[[Any, Buffer], Any]]]
RegexResult = tuple[re.Match, Buffer, callable]
Token = tuple[str, str]  # (type, value)


class Rewindable:
    def __init__(self, text, it):
        self.it = it
        self.text = text
        self.rewinded = []
        self.emitted = []

    def __iter__(self):
        return self

    def rewind(self):
        self.rewinded = self.emitted
        self.emitted = []

    def consume(self):
        self.rewinded = []

    def __next__(self):
        if self.rewinded:
            nxt, self.rewinded = self.rewinded[0], self.rewinded[1:]
        else:
            nxt = next(self.it)
        self.emitted.append(nxt)
        print("nxt", nxt)
        return nxt

    def current_token(self):
        try:
            return self.emitted[-1]
        except IndexError:
            pass

    def __repr__(self):
        return f"Rewindable({self.text}, emmitedd={self.emitted}, rewinded={self.rewinded})"


def regex_iter(string, *patterns):
    print(f"regex_iter {string}, {patterns}")
    pos = 0
    l = len(string)
    _patterns = (re.compile(p) if isinstance(p, str) else p for p in patterns)
    for p in _patterns:
        if p is ...:
            print("yield from")
            res = yield from regex_iter(string, *patterns)
            _, pos = res.span()
            print(f"yield from returned {res}")
            string = string[pos + 1 :]
        elif callable(p):
            result = p(string)
            if result is not None:
                try:
                    res, string = result
                    yield p.__name__, res
                except ValueError:
                    __import__("ipdb").set_trace()
        else:
            res = p.match(string)
            if res is not None:
                _, pos = res.span()
                string = string[pos + 1 :]
                print(f"yield {p.pattern} {res.group(0)}")
                yield p.pattern, res
            else:
                raise RuntimeError(
                    f'Unexpected input "{string}" for parser {p.pattern}'
                )
    if string:
        print(f"still has input {string}")
        raise RuntimeError(f'Run out of parsers but still have input "{string}"')
    yield ("END", None)


def _seq(*patterns):
    def __seq(string):
        print("__seq ", string, patterns)
        result = []
        pos = 0
        for p in patterns:
            res = re.match(p, string)
            if res is not None:
                print("__seq match", res, string)
                pos = res.span()[1]
                string = string[pos + 1 :]
                result.append(res)
            else:
                return None
        print("__seq return", result)
        return result, string

    return __seq


def _let(string):
    print("_let", string)
    string = string.strip()
    res = _seq("let", "\w+")(string)
    if res is not None:
        print("found let <id>")
        res, string = res
        id_ = res[1].group(0)
        equals = re.match("=", string)
        if equals is not None:
            print("found =")
            equals, string = equals, string[1:]
            leteq = _let(string)
            if leteq is not None:
                leteq, string = leteq
                print("found let after = ", leteq)
                in_ = re.match("in", string)
                if in_ is not None:
                    string = string[in_.span()[1] + 1 :]
                    letres = _let(string)
                    if letres is not None:
                        letres, string = letres
                        return ("let", id_, "=", leteq, "in", letres), string

        in_ = re.search("in", string)
        if in_ is not None:
            print("found in")
            string = string[in_.span()[1] + 1 :]
            letres = _let(string)
            if letres is not None:
                letres, string = letres
                print("found let", letres)
                return ("let", id_, "in", letres), string

    else:
        res = not_in(string)
        if res is not None:
            res, string = res
            return res, string
    print("_let return 4")


def not_in(string):
    pos = 0
    res = re.search("in|$", string)
    if res is not None:
        s = res.span()
        return string[: s[0]], string[s[0] :]


print(
    list(
        regex_iter("let a = 1 in let b = 2 in let f = let x in x + 1 in f(a + b)", _let)
    )
)


def tokens(input_):
    def _tokens():
        it = re.finditer(r"([\(\)=]|\w+)", input_)
        for match in it:
            token = match.group(1)
            if token == "let":
                yield ("LET", token)
            elif token == "in":
                yield ("IN", token)
            elif token == "=":
                yield ("EQUAL", token)
            elif token == "end":
                yield ("END", token)
            elif re.match(r"\(", token):
                yield ("LPAR", token)
            elif re.match(r"\)", token):
                yield ("RPAR", token)
            else:
                if re.match(r"([a-z]+)$", token):
                    yield ("ID", token)
                else:
                    yield ("ANYTHING", token)

    it = _tokens()
    result = []
    for typ, value in it:
        if typ in ("ANYTHING", "ID"):
            while typ in ("ANYTHING", "ID"):
                try:
                    result.append((typ, value))
                    typ, value = next(it)
                except StopIteration:
                    break

            if len(result) == 1:
                yield result[0]
            else:
                yield ("ANYTHING", " ".join(r[1] for r in result))

            # we found an non-ANYTHING
            if typ != "ANYTHING":
                yield typ, value
            result = []
        else:
            yield typ, value


def token(
    name,
):
    @wraps(token)
    def inner(input_, buffer_: Buffer):
        if next(input_)[0] == name:
            input_.consume()
            return name
        input_.rewind()

    return inner


def tokenval(tokenname):
    @wraps(tokenval)
    def inner(input_, _):
        token = next(input_)
        if token[0] == tokenname:
            print("tokenval succ ", tokenname)
            input_.consume()
            return token[1]
        input_.rewind()

    return inner


class Token:
    def __init__(self, name):
        self.name = name

    def __call__(self, input_, _):
        token = next(input_)
        if token[0] == self.name:
            input_.consume()
            return token[1]
        input_.rewind()

    def __repr__(self):
        return self.name


LET = Token(r"LET")
IN = Token(r"IN")
EQUAL = Token("EQUAL")
END = Token("END")
LPAR = Token(r"LPAR")
RPAR = Token(r"RPAR")
ID = Token("ID")
ANYTHING = Token("ANYTHING")


class LetAtom:
    def __call__(self, input_, buffer_):
        return or_(input_, buffer_, ID, ANYTHING, let)

    def __repr__(self):
        return self.__class__.__name__


def let(input_, buffer_) -> str:
    print("let")
    token = next(input_)
    if token[0] == "LET":
        id_ = next(input_)
        if id_[0] == "ID":
            eq_in = next(input_)
            if eq_in[0] == "EQUAL":
                eq_res = let(input_, buffer_)
                in_ = next(input_)
                if in_[0] == "IN":
                    return ("let", {id_[1]: eq_res}, let(input_, buffer_))
            elif eq_in[0] == "IN":
                return ("let", id_[1], let(input_, buffer_))
            elif eq_in[0] == "ANYTHING":
                return id_[1]
    elif token[0] == "LPAR":
        exp = let(input_, buffer_)
        rpar = next(input_)  # pop RPAR
        if rpar[0] != "RPAR":
            raise RuntimeError(f"Parse error unexpected token, expecting RPAR {rpar})")
        return exp
    elif token[0] == "ID":
        return token[1]
    elif token[0] == "ANYTHING":
        return token[1]

    raise RuntimeError("Parse error unexpected ", token)


def seq(input_, buffer_, *parsers) -> List[str]:
    result = []
    print("seq start", parsers)

    for p in parsers:
        res = p(input_, buffer_)
        print(f"seq {res}")
        if res is None:
            print(f"seq fail")
            return None
        print("seq succ", res)
    return result


def or_(input_, buffer_, *parsers) -> Optional[Any]:
    print(f"or")
    res = None
    for p in parsers:
        res = p(input_, buffer_)
        if res is not None:
            print(f"or succ")
            return res
    print("or fail")


# main
def letrecdec_parse(input_, parser) -> Any:
    import io

    buffer_ = io.StringIO()
    it = Rewindable(input_, tokens(input_))
    return parser(it, buffer_)


# print(letrecdec_parse("let inc = let x in x + 1 in inc(1)", let))


grammar = """
    ?start : let
    ?let : "let" ID ("=" let)? "in" let | atom
    ?atom : ANYTHING -> anything| "(" let ")"
    ID : /[a-z]+/
    ANYTHING : /(?<!let).+/

    %import common.WS
    %ignore WS
"""

let_parser = Lark(grammar, parser="lalr")


def parse(input_):
    res = let_parser.parse(input_)
    return Transmformator().transform(res)


class Transmformator(LarkTransformer):
    def let(self, tree):
        l = len(tree)
        if l == 6:
            return astlib.let(**{tree[1], tree[3]})(tree[5])
        elif l == 4:
            return astlib.letargs(tree[1])(tree[3])
        else:
            return tree[0]

    def anything(self, tree):
        return e(tree[0].value)


# parse("let a = 1 in a").dump()
# parse("let a = 1 in (let b = 2 in a)").dump()
# parse("let a = let b = 2 in b in print(a)").dump()
