from collections import defaultdict, UserDict
from abc import ABC, abstractmethod
from typing import (
    cast,
    List,
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
TypeEnv = Dict[str, "TTerm"]


class TTerm:
    "Type term"

    refined = False

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

    def __eq__(self, other):
        return isinstance(other, TArrow) and self.t1 == other.t1 and self.t2 == other.t2

    def __hash__(self):
        return hash(self.t1) + hash(self.t2)


class TPoly(TTerm):
    def __init__(self, name):
        self.name = name

    def unify_eq(self, other):
        return other.__class__ is TPoly and self.name == other.name

    def __eq__(self, other):
        return other.__class__ is self.__class__ and self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"'{self.name}"


class TMono(TTerm):
    def __init__(self, val):
        self.val = val

    def unify_eq(self, other):
        return self.__class__ is other.__class__ and self.val == other.val

    def __eq__(self, other):
        return other.__class__ is self.__class__ and self.val == other.val

    def __hash__(self):
        return hash(self.name)

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


def __unify(x: TTerm, y: TTerm, subst: Optional[Subst]) -> Optional[Subst]:
    # print(f"unify({x}, {y}, {subst})")
    if subst is None:
        return None
    elif x.unify_eq(y):
        return subst
    elif isinstance(x, TPoly):
        return __unify_var(x, y, subst)
    elif isinstance(y, TPoly):
        return __unify_var(y, x, subst)
    elif isinstance(x, TArrow) and isinstance(y, TArrow):
        subst = __unify(x.t1, y.t1, subst)
        subst = __unify(x.t2, y.t2, subst)
        return subst
    else:
        return None


def __unify_var(v: TPoly, x: TTerm, subst: Subst) -> Optional[Subst]:
    # print(f"unify_var({v}, {x}, {subst})")
    if v.name in subst:
        return __unify(subst[v.name], x, subst)
    elif isinstance(x, TPoly) and x.name in subst:
        return __unify(v, subst[x.name], subst)
    elif __occurs_check(v, x, subst):
        return None
    else:
        return {**subst, v.name: x}


def __occurs_check(v: TPoly, term: TTerm, subst: Subst) -> bool:
    if v == term:
        return True
    elif isinstance(term, TPoly) and term.name in subst:
        return __occurs_check(v, subst[term.name], subst)
    elif isinstance(term, TArrow):
        return __occurs_check(v, term.t1, subst) or __occurs_check(v, term.t2, subst)
    else:
        return False


lamb_grammar = r"""
    ?start  : let
    ?let    : "let" ID "=" let "in" let | lamb
    ?lamb   : "λ" lvar [":" type] "." let | appl
    ?appl   : appl var | var
    lvar    : VAR
    ?var    : "(" lamb ")" | ID -> id_ | VAR -> var
    ?type   : (VAR | TCONST) "->" type | "'" VAR -> tvar | TCONST -> tconst
    VAR     : /[a-z]/
    ID      : /[a-z_][a-zA-Z_']*/
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
    def __init__(self, typeenv: TypeEnv):
        self.typeenv = typeenv

    @abstractmethod
    def var(self, var: "LVar"):
        ...

    @abstractmethod
    def lamb(self, tree: "LLamb"):
        ...

    @abstractmethod
    def appl(self, tree: "LAppl"):
        ...

    @abstractmethod
    def let(self, tree: "LLet"):
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
        return f"{self.name}"

    def accept(self, visitor: LAVisitor):
        visitor.var(self)
        return self


class LLet(LTerm):
    def __init__(
        self, var: str, e1: LTerm, e2: LTerm, typ: Optional[Union[TPoly, TMono]] = None
    ):
        self.var = var
        self.typ = typ
        self.e1 = e1
        self.e2 = e2

    def __repr__(self):
        return f"(let {self.var} = {self.e1} in {self.e2}):{self.typ}"

    def accept(self, visitor: LAVisitor):
        visitor.let(self)
        self.e1.accept(visitor)
        self.e2.accept(visitor)
        return self


class LLamb(LTerm):
    def __init__(self, var: LVar, body: LTerm, typ: Optional[TArrow] = None):
        self.var = var
        self.body = body
        self.typ = typ

    def __repr__(self):
        return f"(λ{self.var}:{self.var.typ}.{self.body}):{self.typ}"

    def accept(self, visitor):
        visitor.lamb(self)
        self.body.accept(visitor)
        return self


class LAppl(LTerm):
    def __init__(self, e1: LTerm, e2: LTerm):
        self.e1 = e1
        self.e2 = e2
        self.typ: Optional[Union[TPoly, TMono]] = None

    def __repr__(self):
        return f"({self.e1} {self.e2})"

    def accept(self, visitor):
        visitor.appl(self)
        self.e1.accept(visitor)
        self.e2.accept(visitor)
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

    def let(self, tree):
        return LLet(tree[0].value, tree[1], tree[2])

    def id_(self, tree):
        return LVar(tree[0].value)


class SemantVisitor(LAVisitor):
    def var(self, var: LVar):
        return var

    def lamb(self, lamb: LLamb):
        return lamb

    def appl(self, appl):
        return appl

    def let(self, let):
        return let


def unify(constr: Dict[Any, Any]) -> Optional[Subst]:
    if not constr:
        return {}
    k, v = constr.popitem()
    if k == v:
        return unify(constr)
    elif isinstance(k, TPoly):
        if ocurrs(k, v):
            return None
        return unify(constr)
    elif isinstance(v, TPoly):
        if ocurrs(v, k):
            return None
        return unify(constr)
    elif isinstance(k, TArrow) and isinstance(v, TArrow):
        constr[k.t1] = v.t1
        constr[k.t2] = v.t2
        return unify(constr)
    else:
        return None


def ocurrs(needle, haystack) -> bool:
    if needle == haystack:
        return True
    elif isinstance(haystack, TArrow):
        if ocurrs(needle, haystack.t1):
            return True
        elif ocurrs(needle, haystack.t2):
            return True
        else:
            return False
    else:
        return False


def substitute2(s: Dict[Any, Any], constr: Dict[Any, Any]):
    for sk, sv in s.items():
        constr[sk] = sv
    return constr


def infer_type(env: TypeEnv, term: LTerm) -> TTerm:
    "Type inference Algorithm J"
    if isinstance(term, LVar):
        if term.typ is None:
            if term.name in env:
                term.typ = env[term.name]
            else:
                term.typ = TPoly(newvar())
                env[term.name] = term.typ
        return cast(TTerm, term.typ)
    elif isinstance(term, LAppl):
        a = infer_type(env, term.e1)
        b = infer_type(env, term.e2)
        at = TArrow(b, TPoly(newvar()))
        s = unify({a: at})
        if s is None:
            raise TypeError
        term.e1.typ = at
        term.e2.typ = at.t1
        if (
            isinstance(term.e1, LVar)
            # This is a shamefull workaround to
            # get types printed right
            and hasattr(term.e1, "name")
            and hasattr(env[term.e1.name], "lamb")
        ):
            env[term.e1.name].lamb.var.typ = at  # type: ignore
        term.typ = at.t2
        return cast(TTerm, term.typ)
    elif isinstance(term, LLamb):
        term.var.typ = TPoly(newvar())
        env[term.var.name] = term.var.typ
        # workarrow to fix lambda var after refinement
        env[term.var.name].lamb = term  # type: ignore
        term.body.typ = infer_type(env, term.body)
        term.typ = TArrow(term.var.typ, term.body.typ)
        return term.typ
    elif isinstance(term, LLet):
        a_ = infer_type(env, term.e1)
        env[term.var] = a_
        b_ = infer_type(env, term.e2)
        term.typ = b_
        return term.typ
    else:
        raise TypeError


def lamb_parse(input_: str) -> LTerm:
    resetvars()
    typeenv: TypeEnv = {}
    res = LambTransformer().transform(lamb_parser.parse(input_))
    # res.accept(SemantVisitor(typeenv))
    typ = infer_type(typeenv, res)
    res.typ = typ
    return res


# print(lamb_parse("(λx.λy.x) u v"))
# print(lamb_parse("(λx.x) u"))
# print(lamb_parse("(λx.x a)(λy.y)"))
print(lamb_parse("(λx.x)"))
print(lamb_parse("(λx.y)"))
print(lamb_parse("(λx.λy.x)"))
print(lamb_parse("(λx.λy.x) a b"))
print(lamb_parse("let id = (λx.x) in id a"))
