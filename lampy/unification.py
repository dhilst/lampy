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

from lark import Lark, Transformer as LarkTransformer

Subst = Dict[str, "TTerm"]


class TTerm:
    "Type term"

    def unify_eq(self, other) -> bool:
        pass


class TArrow(TTerm):
    def __init__(self, t1, t2):
        self.t1 = t1
        self.t2 = t2

    def unify_eq(self, other) -> bool:
        return (
            other.__class__ is TArrow
            and self.t1.unify_eq(other.t1)
            and self.t2.unify_eq(other.t2)
        )

    def __repr__(self):
        return f"({self.t1} -> {self.t2})"


class TPoly(TTerm):
    def __init__(self, name):
        self.name = name

    def unify_eq(self, other):
        return other.__class__ is TPoly and self.name == other.name

    def __eq__(self, other):
        return other.__class__ is self.__class__ and self.name == other.name

    def __repr__(self):
        return self.name


class TMono(TTerm):
    def __init__(self, val):
        self.val = val

    def unify_eq(self, other):
        return self.__class__ is other.__class__ and self.val == other.val

    def __eq__(self, other):
        return other.__class__ is self.__class__ and self.val == other.val

    def __repr__(self):
        return self.val


class TUnification:
    def __init__(self, t1: TTerm, t2: TTerm):
        self.t1 = t1
        self.t2 = t2

    def unify(self):
        return unify(self.t1, self.t2, {})

    def __repr__(self):
        return f"unify({self.t1}, {self.t2})"


def unify(x: TTerm, y: TTerm, subst: Optional[Subst]) -> Optional[Subst]:
    print(f"unify({x}, {y}, {subst})")
    if subst is None:
        return None
    elif x.unify_eq(y):
        return subst
    elif isinstance(x, TPoly):
        return unify_var(x, y, subst)
    elif isinstance(y, TPoly):
        return unify_var(y, x, subst)
    elif isinstance(x, TArrow) and isinstance(y, TArrow):
        subst = unify(x.t1, y.t1, subst)
        subst = unify(x.t2, y.t2, subst)
        return subst
    else:
        return None


def unify_var(v: TPoly, x: TTerm, subst: Subst) -> Optional[Subst]:
    print(f"unify_var({v}, {x}, {subst})")
    if v.name in subst:
        return unify(subst[v.name], x, subst)
    elif isinstance(x, TPoly) and x.name in subst:
        return unify(v, subst[x.name], subst)
    elif occurs_check(v, x, subst):
        return None
    else:
        return {**subst, v.name: x}


def occurs_check(v: TPoly, term: TTerm, subst: Subst) -> bool:
    if v == term:
        return True
    elif isinstance(term, TPoly) and term.name in subst:
        return occurs_check(v, subst[term.name], subst)
    elif isinstance(term, TArrow):
        return occurs_check(v, term.t1, subst) or occurs_check(v, term.t2, subst)
    else:
        return False


unification_grammar = r"""
    unification : term "==" term
    ?term       : tarrow | POLY -> poly | MONO -> mono
    ?tarrow     : term "->" term | "(" term ")"
    POLY        : /[a-z]/
    MONO        : /(int|str|bool)/

    %import common.WS
    %import common.SH_COMMENT
    %import common.INT
    %ignore WS
    %ignore SH_COMMENT
"""

unification_parser = Lark(unification_grammar, start="unification", parser="lalr")


class UnificationTransformer(LarkTransformer):
    def unification(self, tree):
        return TUnification(tree[0], tree[1])

    def poly(self, tree):
        return TPoly(tree[0].value)

    def mono(self, tree):
        return TMono(tree[0].value)

    def tarrow(self, tree):
        return TArrow(tree[0], tree[1])


def unification_parse(input_):
    return UnificationTransformer().transform(unification_parser.parse(input_))


print(unification_parse("a -> b == int -> int").unify())

lamb_grammar = r"""
    ?start  : term
    ?term   : lamb
    ?lamb   : "λ" VAR [":" type] "." term | appl
    ?appl   : appl term | var
    ?var    : "(" term ")" | VAR -> var
    ?type   : (VAR | TCONST) "->" type | VAR -> tvar | TCONST -> tconst
    VAR     : /[a-z]/
    TCONST  : /(int|bool|str)/

    %import common.WS
    %ignore WS
"""

lamb_parser = Lark(lamb_grammar, parser="lalr")


def lamb_parse(input_: str):
    return LambTransformer().transform(lamb_parser.parse(input_))


class LTerm:
    ...


class LVar(LTerm):
    def __init__(self, name: str, typ: Optional[Union[TPoly, TMono]] = None):
        self.name = name
        self.typ = typ

    def __repr__(self):
        return f"{self.name}:{self.typ}"


class LLamb(LTerm):
    def __init__(self, var: LVar, body: LTerm, typ: Optional[TArrow] = None):
        self.var = var
        self.body = body
        self.typ = typ

    def __repr__(self):
        return f"(λ{self.var}.{self.body}):{self.typ}"


class LAppl(LTerm):
    def __init__(self, e1: LTerm, e2: LTerm):
        self.e1 = e1
        self.e2 = e2
        self.typ: Optional[Union[TPoly, TMono]] = None

    def __repr__(self):
        return f"({self.e1} {self.e2}):{self.typ}"


class LambTransformer(LarkTransformer):
    def lamb(self, tree):
        var, *typ, body = tree
        return LLamb(var, body, typ[0] if typ else None)

    def var(self, tree):
        return LVar(tree[0].value)

    def appl(self, tree):
        return LAppl(tree[0], tree[1])


print(lamb_parse("(λx.x) a"))
