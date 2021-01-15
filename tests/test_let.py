
from lampy.letparser import parse

def test_letdef():
    assert parse("""let def foo = 1 in foo()""").eval() == 1

