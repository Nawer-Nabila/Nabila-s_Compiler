# ============================================================
# PHASE 1 — LEXER (Tokenizer)
# Mini C Compiler
# ============================================================

KEYWORDS = {'int', 'float', 'void', 'return', 'if', 'else', 'while', 'char'}

OPERATORS = {
    '==': 'EQ', '!=': 'NEQ', '<=': 'LE', '>=': 'GE',
    '<':  'LT',  '>':  'GT',  '=': 'ASSIGN',
    '+':  'PLUS', '-': 'MINUS', '*': 'MUL', '/': 'DIV'
}

PUNCTS = {
    '(': 'LPAREN',  ')': 'RPAREN',
    '{': 'LBRACE',  '}': 'RBRACE',
    ';': 'SEMICOLON', ',': 'COMMA'
}


def lex(src: str) -> list[dict]:
    tokens = []
    i = 0
    n = len(src)

    while i < n:
        # skip whitespace
        if src[i].isspace():
            i += 1
            continue

        # line comment
        if src[i:i+2] == '//':
            while i < n and src[i] != '\n':
                i += 1
            continue

        # block comment
        if src[i:i+2] == '/*':
            i += 2
            while i < n and src[i:i+2] != '*/':
                i += 1
            i += 2
            continue

        # string literal
        if src[i] == '"':
            s = '"'
            i += 1
            while i < n and src[i] != '"':
                s += src[i]
                i += 1
            s += '"'
            i += 1
            tokens.append({'type': 'STRING_LITERAL', 'val': s})
            continue

        # number
        if src[i].isdigit():
            num = ''
            while i < n and (src[i].isdigit() or src[i] == '.'):
                num += src[i]
                i += 1
            tok_type = 'FLOAT_LITERAL' if '.' in num else 'INT_LITERAL'
            tokens.append({'type': tok_type, 'val': num})
            continue

        # identifier / keyword
        if src[i].isalpha() or src[i] == '_':
            ident = ''
            while i < n and (src[i].isalnum() or src[i] == '_'):
                ident += src[i]
                i += 1
            if ident in KEYWORDS:
                tokens.append({'type': ident.upper(), 'val': ident})
            else:
                tokens.append({'type': 'IDENTIFIER', 'val': ident})
            continue

        # two-char operators
        two = src[i:i+2]
        if two in OPERATORS:
            tokens.append({'type': OPERATORS[two], 'val': two})
            i += 2
            continue

        # single-char operators
        if src[i] in OPERATORS:
            tokens.append({'type': OPERATORS[src[i]], 'val': src[i]})
            i += 1
            continue

        # punctuation
        if src[i] in PUNCTS:
            tokens.append({'type': PUNCTS[src[i]], 'val': src[i]})
            i += 1
            continue

        i += 1  # unknown char, skip

    return tokens


def print_tokens(tokens: list[dict]):
    KW_TYPES  = {'INT','FLOAT','VOID','RETURN','IF','ELSE','WHILE','CHAR'}
    LIT_TYPES = {'INT_LITERAL','FLOAT_LITERAL','STRING_LITERAL'}
    OP_TYPES  = {'PLUS','MINUS','MUL','DIV','ASSIGN','EQ','NEQ','LT','GT','LE','GE'}
    PNC_TYPES = {'LPAREN','RPAREN','LBRACE','RBRACE','SEMICOLON','COMMA'}

    kw_count  = sum(1 for t in tokens if t['type'] in KW_TYPES)
    id_count  = sum(1 for t in tokens if t['type'] == 'IDENTIFIER')

    print("=" * 55)
    print("  PHASE 1 — LEXER / TOKEN STREAM")
    print("=" * 55)
    print(f"  Total Tokens : {len(tokens)}")
    print(f"  Keywords     : {kw_count}")
    print(f"  Identifiers  : {id_count}")
    print("-" * 55)
    print(f"  {'#':<5} {'Type':<20} {'Value'}")
    print("-" * 55)

    for idx, tok in enumerate(tokens, 1):
        t, v = tok['type'], tok['val']
        if t in KW_TYPES:
            label = '[KW]'
        elif t == 'IDENTIFIER':
            label = '[ID]'
        elif t in LIT_TYPES:
            label = '[LIT]'
        elif t in OP_TYPES:
            label = '[OP]'
        elif t in PNC_TYPES:
            label = '[PNC]'
        else:
            label = ''
        print(f"  {idx:<5} {t:<20} {v!r:<15} {label}")

    print("=" * 55)
