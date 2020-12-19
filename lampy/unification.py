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
        if isinstance(self.t1, TArrow):
            return f"({self.t1}) -> {self.t2}"
        return f"{self.t1} -> {self.t2}"


class TPoly(TTerm):
    def __init__(self, name):
        self.name = name

    def unify_eq(self, other):
        return other.__class__ is TPoly and self.name == other.name

    def __eq__(self, other):
        return other.__class__ is self.__class__ and self.name == other.name

    def __repr__(self):
        return f"'{self.name}"


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
    # print(f"unify({x}, {y}, {subst})")
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
    # print(f"unify_var({v}, {x}, {subst})")
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


lamb_grammar = r"""
    ?start  : lamb 
    ?lamb   : "λ" lvar [":" type] "." lamb | appl
    ?appl   : appl var | var
    lvar    : VAR
    ?var    : "(" lamb ")" | VAR -> var
    ?type   : (VAR | TCONST) "->" type | "'" VAR -> tvar | TCONST -> tconst
    VAR     : /[a-z]/
    TCONST  : /(int|bool|str)/

    %import common.WS
    %ignore WS
"""

lamb_parser = Lark(lamb_grammar, parser="lalr")


from string import ascii_lowercase

bound_vars = []
free_vars = list(ascii_lowercase)


# oh no
def newvar() -> str:
    global bound_vars, free_vars
    v = free_vars[0]
    del free_vars[0]
    bound_vars.append(v)
    return v


def freevar(v: str):
    global free_vars, bound_vars
    del bound_vars[bound_vars.index(v)]
    free_vars.append(v)
    free_vars = sorted(free_vars)


def resetvars():
    global free_vars, bound_vars
    bound_vars = []
    free_vars = list(ascii_lowercase)


class LAVisitor(ABC):
    @abstractmethod
    def var(self, var: "LVar"):
        ...

    @abstractmethod
    def lamb(self, tree: "LLamb"):
        ...

    @abstractmethod
    def appl(self, tree: "LAppl"):
        ...


class LTerm:
    typ: Optional[TTerm]

    @abstractmethod
    def accept(self, visitor: LAVisitor) -> "LTerm":
        pass


class LVar(LTerm):
    def __init__(self, name: str, typ: Optional[Union[TPoly, TMono]] = None):
        self.name = name
        self.typ = typ

    def __repr__(self):
        return f"{self.name}:{self.typ}"

    def accept(self, visitor: LAVisitor):
        visitor.var(self)
        return self


class LLamb(LTerm):
    def __init__(self, var: LVar, body: LTerm, typ: Optional[TArrow] = None):
        self.var = var
        self.body = body
        self.typ = typ

    def __repr__(self):
        return f"(λ{self.var}.{self.body}):{self.typ}"

    def accept(self, visitor):
        self.body.accept(visitor)
        visitor.lamb(self)
        return self


class LAppl(LTerm):
    def __init__(self, e1: LTerm, e2: LTerm):
        self.e1 = e1
        self.e2 = e2
        self.typ: Optional[Union[TPoly, TMono]] = None

    def __repr__(self):
        return f"({self.e1} {self.e2}):{self.typ}"

    def accept(self, visitor):
        self.e1.accept(visitor)
        self.e2.accept(visitor)
        visitor.appl(self)
        return self


class LambTransformer(LarkTransformer):
    def lamb(self, tree):
        var, *typ, body = tree
        if typ:
            var.typ = TMono(typ[0])
        return LLamb(var, body)

    def var(self, tree):
        return LVar(tree[0].value)

    def lvar(self, tree):
        return LVar(tree[0].value)

    def appl(self, tree):
        return LAppl(tree[0], tree[1])

    def tconst(self, tree):
        return tree[0].value

    def tvar(self, tree):
        return f"'{tree[0].value}"


class SemantVisitor(LAVisitor):
    def var(self, var: LVar):
        return var

    def lamb(self, lamb: LLamb):
        def bind_var(term, parent=None):
            """
            Search in lamb.body an instance of LVar with the same name of
            lamb.var, if found replace by lamb.var so both are the same
            instance, this way any type anotation propagates at lamb.body
            """
            if isinstance(term, LVar) and term.name == lamb.var.name:
                if isinstance(parent, LLamb):
                    parent.body = lamb.var
                elif isinstance(parent, LAppl):
                    if parent.e2 is term:
                        parent.e2 = lamb.var
                    else:
                        parent.e1 = lamb.var
                elif parent is None:  # first call
                    lamb.body = lamb.var
            elif isinstance(term, LLamb):
                return bind_var(term.body, term)
            elif isinstance(term, LAppl):
                res = bind_var(term.e1, term)
                if res is not None:
                    return
                bind_var(tern.e2, term)

        bind_var(lamb.body)
        return lamb

    def appl(self, appl):
        return appl


class TypeInfVisitor(LAVisitor):
    def var(self, var: LVar):
        if var.typ is None:
            var.typ = TPoly(newvar())
        return var

    def lamb(self, lamb: LLamb):
        if lamb.var.typ is None:
            lamb.var.typ = TPoly(newvar())
        lamb.typ = TArrow(lamb.var.typ, lamb.body.typ)

    def appl(self, appl: LAppl):
        s = unify(appl.e1.typ.t1, appl.e2, {})  # type: ignore
        appl.typ = appl.e1.typ.t2  # type: ignore
        return appl


def lamb_parse(input_: str) -> LTerm:
    resetvars()
    res = LambTransformer().transform(lamb_parser.parse(input_))
    print("FP", res)
    res.accept(SemantVisitor()).accept(TypeInfVisitor())
    return res


print(lamb_parse("(λx.λy.x) u v"))
