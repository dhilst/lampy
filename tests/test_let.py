
from lampy.letparser import parse

def test_letdef():
    assert parse("""let def foo = "hello" in foo()""").eval() == "hello"

