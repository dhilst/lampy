import sys
from sly import Lexer, Parser
from collections.abc import Iterable

# lamb -> LAMB ID DOT term
# lamb -> appl
# appl -> appl term
# appl -> term
# term -> LPAR lamb RPAR
# term -> ID
#
# ID -> [a-z]
# LAMB -> λ
# DOT -> \.
# LPAR -> \(
# RPAR -> \)


class Lex(Lexer):
    tokens = {ARROW, TERMINAL, NONTERMINAL, REGEXP, SEMICOLON}
    ARROW = r"->"
    TERMINAL = r"[A-Z0-9]+"
    NONTERMINAL = r"[a-z0-9]+"
    REGEXP = r"/.*/"
    SEMICOLON = ";"
    ignore = " \t\n"
    ignore_comment = r"\#.*"


def flat(it):
    def _flat(it):
        for i in it:
            if isinstance(i, Iterable) and not isinstance(i, str):
                yield from _flat(i)
            else:
                yield i

    return tuple(_flat(it))


class Par(Parser):
    tokens = Lex.tokens
    debugfile = "bnf.out"

    # rules -> rules rule
    # rules -> rule
    # rule -> terminal_rule SEMICOLON
    # rule -> nonterminal_rule SELICOLON
    # nonterminal_rule -> NONTERMINAL ARROW tokens_
    # terminal_rule -> TERMINAL ARROW REGEXP
    # tokens_ -> tokens token
    # tokens_ -> token
    # token -> TERMINAL
    # token -> NONTERMINAL
    # token -> REGEXP
    # TERMIMAL -> /[A-Z0-9]+/
    # NONTERMINAL -> /[a-z0-9]+/
    # REGEXP -> /\/.*\//

    @_("rules rule")
    def rules(self, p):
        if isinstance(p[0][0], str):
            return (p[0], p[1])
        return (*p[0], p[1])

    @_("rule")
    def rules(self, p):
        return p[0]

    @_("terminal_rule SEMICOLON", "nonterminal_rule SEMICOLON")
    def rule(self, p):
        return p[0]

    @_("NONTERMINAL ARROW tokens_")
    def nonterminal_rule(self, p):
        ts = p[2]
        if isinstance(ts, str):
            return ("nonterminal_rule", p[0], p[2])
        elif isinstance(ts, tuple):
            return ("nonterminal_rule", p[0], *flat(p[2]))

    @_("TERMINAL ARROW REGEXP")
    def terminal_rule(self, p):
        return ("terminal_rule", p[0], p[2])

    @_("tokens_ token")
    def tokens_(self, p):
        if isinstance(p, tuple):
            return (*p[0], p[1])
        return (p[0], p[1])

    @_("token")
    def tokens_(self, p):
        return p[0]

    @_("TERMINAL", "NONTERMINAL", "REGEXP")
    def token(self, p):
        return p[0]


def parse(input_: str):
    return Par().parse(Lex().tokenize(input_))


def gen_parser(parse_results, debugfile):
    from io import StringIO

    header = StringIO()
    lexer = StringIO()
    lexer_body = StringIO()
    lexer_tokens = []
    parser = StringIO()
    parser_body = StringIO()
    footer = StringIO()

    header.write("from sly import Lexer as SlyLexer, Parser as SlyParser\n")
    lexer.write("\n\nclass Lexer(SlyLexer):\n")
    parser.write("\n\nclass Parser(SlyParser):\n    tokens = Lexer.tokens\n")
    parser_body.write(f"    debugfile = '{debugfile}.out'\n")

    for type_, *rule in parse_results:
        if type_ == "terminal_rule":
            token, body = rule
            body = body[1:-1]  # remove //
            lexer_tokens.append(token)
            lexer_body.write(f"    {token} = r'{body}'\n")

        elif type_ == "nonterminal_rule":
            name, *body = rule
            body = " ".join(body)
            parser_body.write(
                f"""
    @_('{body}')
    def {name}(self, p):
        return ('{name}', *p)

"""
            )

    footer.write(
        """\n\ndef parse(input_: str):
    return Parser().parse(Lexer().tokenize(input_))\n"""
    )

    lexer.write(f"    tokens = {{{','.join(lexer_tokens)}}}\n")
    lexer.write(r"    ignore = r' \t'" + "\n")
    lexer.write(lexer_body.getvalue())
    parser.write(parser_body.getvalue())

    return header.getvalue() + lexer.getvalue() + parser.getvalue() + footer.getvalue()


from pprint import pprint

grammar = """
        lamb -> LAMB ID DOT lamb;
        lamb -> appl;
        appl -> appl term;
        appl -> term;
        term -> LPAR lamb RPAR;
        term -> ID;
        ID -> /[a-z]/;
        LPAR -> /\(/;
        RPAR -> /\)/;
        LAMB -> /λ/;
        DOT -> /\./;
        """

def generate_parser(grammar, output_mod):
    with open(f"{output_mod}.py", "w") as out:
        out.write(gen_parser(parse(grammar), output_mod))

    import importlib
    return importlib.import_module(output_mod)

parser = generate_parser(grammar, "lambauto")
pprint(parser.parse("(λx.x)"))
pprint(parser.parse("λx.y"))
pprint(parser.parse("λx.λy.x y"))


