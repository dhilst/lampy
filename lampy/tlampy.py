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
    TypeVar as t_TypeVar,
    Iterable,
    Sequence,
    Tuple,
    Union,
)
import operator as op
from collections import namedtuple
from functools import reduce

from lampy.utils import trace


_bound_vars = set()


def _next_var(v: "Var") -> "Var":
    """
    Return the next letter

    >>> _next_var(Var("u", int))
    v:int

    >>> _next_var(Var("z", int))
    u:int
    """
    global _bound_vars
    first = ord("u")
    last = ord("z")
    index = ord(v.name)
    while True:
        next_ = ord(v.name) + 1
        if next_ > last:
            next_ = first
        found = Var(chr(next_), v.typ)
        if found not in _bound_vars:
            return Var(chr(next_), v.typ)


def _reset_bound_vars():
    global _bound_vars
    _bound_vars = set()


def _bind(var: "Var"):
    _bound_vars.add(var.name)


class Type(ABC):
    typ: Any

    def __repr__(self):
        if self.typ in __builtins__:
            return f"self.typ.__name__"
        return repr(self.typ)


class TypeUnk(Type):
    typ: None
    __name__ = "unk"  # used in Var.repr

    def __repr__(self):
        return "unk"


class TypeVar(Type):  # TypeVar already defined
    def __init__(self, var: str):
        self.typevar = var

    def __repr__(self):
        return f"'{self.typevar}"


class TypeArrow(Type):
    def __init__(self, a: Type, b: Type):
        self.typ = (a, b)
        self.t1 = a
        self.t2 = b


    def __eq__(self, other):
        return self.t1 == other.t1 and self.t2 == other.t2
    def __repr__(self):
        t1 = (
            self.t1.__name__
            if getattr(self.t1, "__name__", None) in __builtins__
            else self.t1
        )
        t2 = (
            self.t2.__name__
            if getattr(self.t2, "__name__", None) in __builtins__
            else self.t2
        )

        if isinstance(t1, TypeArrow):
            t1 = f"({t1})"

        return f"{t1} -> {t2}"


class Term(ABC):
    typ: Any

    @abstractmethod
    def replace(self, old, new) -> "Term":
        pass

    @abstractmethod
    def typecheck(self) -> None:
        "Raises Type error"
        pass

    @property
    def is_norm(self) -> bool:
        """
        Is in beta-normal form?

        >>> Lamb(Var("x", int), Var("x", int)).is_norm
        True
        >>> Var("x", int).is_norm
        True
        >>> Val("1", int).is_norm
        True
        >>> Appl(Lamb(Var("x", int), Var("x", int)), Val("1", int)).is_norm
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

    @abstractmethod
    def bind(self, var, to) -> "Term":
        "Bind a variable var to `to` if in self. Return self, unmodified if no bind should occurr"


class BinOp(Term):
    """
    >>> eval_term(BinOp("+", Val("1", int), Val("1", int)))
    2

    >>> AST(Appl(Lamb(Var("x", int), BinOp("+", Var("x", int), Val("1", int))), Val("2", int))).eval()
    3
    """

    opmap = {
        "+": op.add,
        "*": op.mul,
        "/": op.truediv,
        "-": op.sub,
    }

    def __init__(self, op: str, a: Term, b: Term):
        self.a = a
        self.op = op
        self.b = b
        self.typ = a.typ
        if op not in self.__class__.opmap:
            raise TypeError(f"Unknown operator {op}")

    def typecheck(self) -> None:
        if not self.a.typ == self.b.typ:
            raise TypeError(f"Typecheck failed at {repr(self)}")

    @property
    def opfun(self):
        return self.__class__.opmap[self.op]

    def replace(self, old, new):
        self.a = self.a.replace(old, new)
        self.b = self.b.replace(old, new)
        return self

    def __repr__(self):
        return f"{self.a} {self.op} {self.b}"

    def bind(self, var, to):
        self.a = self.a.bind(var, to)
        self.b = self.b.bind(var, to)
        return self


class Var(Term):
    def __init__(self, name, typ):
        self.name = name
        self.typ = typ

    def typecheck(self) -> None:
        pass

    def __repr__(self):
        if isinstance(self.typ, TypeArrow):
            return f"{self.name}:{self.typ}"
        return f"{self.name}:{self.typ.__name__}"

    def replace(self, old, new) -> "Term":
        if self.name == old.name:
            return new
        return self

    def bind(self, var, to):
        if self.name == var.name:
            self.bound = to
            self.typ = to.var.typ
        return self


class Val(Term):
    def __init__(self, val, typ):
        self.val = typ(val)
        self.typ = typ

    def __repr__(self):
        return str(self.val)

    def replace(self, old, new) -> "Term":
        return self

    def typecheck(self) -> None:
        pass

    def bind(self, var, to):
        return self


class Lamb(Term):
    body: Term

    def __init__(self, var: Var, body: Term):
        self.var = var
        self.body = body
        self.body = self.body.bind(var, self)
        self.typ = TypeArrow(var.typ, body.typ)
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

    def typecheck(self) -> None:
        self.body.typecheck()

    def scope(self):
        return self.body

    def bind(self, var, to):
        self.body = self.body.bind(var, to)
        self.typ.t2 = self.body.typ  # update return type that may be unknow
        return self


class Appl(Term):
    def __init__(self, e1, e2):
        self.e1 = e1
        self.e2 = e2
        self.typ = e2.typ

    def replace(self, old, new):
        self.e1 = self.e1.replace(old, new)
        self.e2 = self.e2.replace(old, new)
        return self

    def __repr__(self):
        if isinstance(self.e2, Appl):
            return f"{self.e1} ({self.e2})"
        return f"{self.e1} {self.e2}"

    def typecheck(self) -> None:
        self.e1.typecheck()
        self.e1.typecheck()
        if not self.e1.typ.t1 == self.e2.typ:
            raise TypeError(f"Typecheck failed at {self}")

    def bind(self, var, to):
        self.e1 = self.e1.bind(var, to)
        self.e2 = self.e2.bind(var, to)
        self.typ = self.e2.typ
        return self


def appl(lam: "Lamb", term: Term, i=0):
    """
    >>> appl(Lamb(Var("x", int), Var("x", int)), Val("1", int))
    1
    >>> appl(Lamb(Var("x", int), Lamb( Var("y", int), Appl(Var("x", int), Var("y", int)) )), Val("1", int))
    (λy:int.1 y:int)

    # This should raise type error but here the typechecking would already happen
    >>> appl(Lamb(Var("x", int), Lamb( Var("y", int), Appl(Var("x", int), Var("y", int)) )), Var("y", int))
    (λz:int.y:int z:int)

    >>> appl(Lamb(Var("x", int), Var("x", int)), Lamb(Var("y", int), Var("y", int)))
    (λy:int.y:int)
    """
    res = lam.replace(lam.var, term)
    if isinstance(res, Lamb):
        trace(f"appl({lam}, {term}) => {res.body}", i)
        return res.body

    raise TypeError(f"{res} is not a lambda")


def eval_term(term: Term, i=0, *, _trace=False) -> Term:
    """
    Abstration evaluate to it self
    >>> eval_term(Lamb(Var("x", int), Var("x", int)))
    (λx:int.x:int)

    Value evaluate to it self
    >>> eval_term(Appl(Lamb(Var("x", int), Var("x", int)), Val("1", int)))
    1

    Application evalute by CBV
    >>> eval_term(Appl(Lamb(Var("x", int), Var("x", int)), Lamb(Var("y", int), Var("y", int))))
    (λy:int.y:int)
    """
    trace(f"eval({term})", i, _trace=_trace)
    if isinstance(term, Appl):
        e1 = eval_term(term.e1, i + 1, _trace=_trace)
        e2 = eval_term(term.e2, i + 1, _trace=_trace)
        if isinstance(e1, Lamb):
            return eval_term(appl(e1, e2, i + 1), i + 1, _trace=_trace)
    elif isinstance(term, BinOp):
        a = eval_term(term.a, i + 1, _trace=_trace)
        b = eval_term(term.b, i + 1, _trace=_trace)

        if isinstance(a, Val) and isinstance(b, Val):
            res = term.opfun(a.val, b.val)
            return Val(res, type(res))

    return term


class AST:
    def __init__(self, root: Term):
        self.root = root

    def typecheck(self) -> None:
        """
        >>> AST(
        ...     Appl(Lamb(Var("x", int), Var("x", int)), Var("a", str))
        ... ).typecheck()
        Traceback (most recent call last):
            ...
        TypeError: Typecheck failed at (λx:int.x:int) a:str

        >>> AST(
        ...     Appl(Lamb(Var("x", int), Var("x", int)), Var("a", int))
        ... ).typecheck()

        >>> BinOp("+", Var("x", str), Val("1", int)).typecheck()
        Traceback (most recent call last):
            ...
        TypeError: Typecheck failed at x:str + 1
        """
        self.root.typecheck()

    def eval(self, _trace=False):
        _reset_bound_vars()
        t = eval_term(self.root, _trace=_trace)
        prev = None
        while not t.is_norm:
            prev = t
            t = eval_term(t, _trace=_trace)
            if prev == t:
                break
        return t
