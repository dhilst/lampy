
from lampy.letparser import parse

def test_mul():
    assert parse("2 * 2").eval() == 4

def test_letdef():
    assert parse("""let def foo = 1 in foo()""").eval() == 1

def test_bool_expr():
    assert parse("""1 == 1""").eval() == True

def test_ift_expr():
    assert parse("""1 if true else 0""").eval()  == 1
    assert parse("""1 if false else 0""").eval()  == 0

def test_fact():
    assert parse("let def fact n = 1 if n == 0 else n * fact(n - 1) in fact(5)").eval() == 120

def test_match():
    # Test default case
    assert parse('match 1 with | _ => 1 end').eval() == 1

    # Test simple case
    assert parse('match 1 with | 1 => 1 end').eval() == 1

    # Test list match
    assert parse('match ([1, 2]) with | [] => [] | a, *b => a end').eval() == 1
