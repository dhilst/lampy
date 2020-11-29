from functools import wraps

def cache(f):
    """
    Caches the return of a function

    >>> a = 0
    >>> def f():
    ...     global a
    ...     a += 1
    ...     return a
    >>> g = cache(f)
    >>> g()
    1
    >>> g()
    1
    >>> a = 10
    >>> g()
    1
    """
    _cache = None
    @wraps(f)
    def _(*args, **kwargs):
        nonlocal _cache
        if _cache is None:
            _cache = f(*args, **kwargs)
        return _cache
    return _

