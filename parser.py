# ============================================================
# PHASE 2 — PARSER  (builds Abstract Syntax Tree)
# Mini C Compiler
# ============================================================


class ParseError(Exception):
    pass


def parse(tokens: list[dict]):
    pos = [0]   # mutable pointer

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else {'type': 'EOF', 'val': ''}

    def consume(expected_type=None):
        t = tokens[pos[0]] if pos[0] < len(tokens) else {'type': 'EOF', 'val': ''}
        if expected_type and t['type'] != expected_type:
            raise ParseError(
                f"Expected {expected_type}, got {t['type']} ('{t['val']}')"
            )
        pos[0] += 1
        return t

    def match(tok_type):
        if peek()['type'] == tok_type:
            pos[0] += 1
            return True
        return False

    # ── grammar rules ──────────────────────────────────────────

    def parse_program():
        node = {'type': 'PROGRAM', 'children': []}
        while peek()['type'] != 'EOF':
            node['children'].append(parse_func_def())
        return node

    def parse_type():
        t = peek()['type']
        if t in ('INT', 'FLOAT', 'VOID', 'CHAR'):
            pos[0] += 1
            return t.lower()
        raise ParseError(f"Expected type keyword, got {t}")

    def parse_func_def():
        rtype = parse_type()
        name = consume('IDENTIFIER')['val']
        consume('LPAREN')
        params = {'type': 'PARAM_LIST', 'children': []}
        while peek()['type'] != 'RPAREN':
            pt = parse_type()
            pn = consume('IDENTIFIER')['val']
            params['children'].append({'type': 'PARAM', 'sval': pn,
                                        'data_type': pt, 'children': []})
            if not match('COMMA'):
                break
        consume('RPAREN')
        block = parse_block()
        return {'type': 'FUNC_DEF', 'sval': name, 'data_type': rtype,
                'children': [params, block]}

    def parse_block():
        consume('LBRACE')
        stmts = {'type': 'STMT_LIST', 'children': []}
        while peek()['type'] not in ('RBRACE', 'EOF'):
            s = parse_stmt()
            if s:
                stmts['children'].append(s)
        consume('RBRACE')
        return {'type': 'BLOCK', 'children': [stmts]}

    def parse_stmt():
        t = peek()['type']
        if t in ('INT', 'FLOAT', 'VOID', 'CHAR'):
            return parse_var_decl_line()
        if t == 'RETURN':
            return parse_return()
        if t == 'IF':
            return parse_if()
        if t == 'WHILE':
            return parse_while()
        if t == 'LBRACE':
            return parse_block()
        if t == 'SEMICOLON':
            pos[0] += 1
            return None
        stmt = parse_expr_stmt()
        consume('SEMICOLON')
        return stmt

    def parse_var_decl_line():
        dt = parse_type()
        stmts = []
        while True:
            name = consume('IDENTIFIER')['val']
            init = None
            if match('ASSIGN'):
                init = parse_expr()
            stmts.append({'type': 'VAR_DECL', 'sval': name, 'data_type': dt,
                           'children': [init] if init else []})
            if not match('COMMA'):
                break
        consume('SEMICOLON')
        if len(stmts) == 1:
            return stmts[0]
        return {'type': 'STMT_LIST', 'children': stmts}

    def parse_return():
        consume('RETURN')
        children = []
        if peek()['type'] != 'SEMICOLON':
            children.append(parse_expr())
        consume('SEMICOLON')
        return {'type': 'RETURN', 'children': children}

    def parse_if():
        consume('IF')
        consume('LPAREN')
        cond = parse_expr()
        consume('RPAREN')
        then = parse_stmt()
        children = [cond, then]
        if peek()['type'] == 'ELSE':
            pos[0] += 1
            children.append(parse_stmt())
        return {'type': 'IF', 'children': children}

    def parse_while():
        consume('WHILE')
        consume('LPAREN')
        cond = parse_expr()
        consume('RPAREN')
        body = parse_stmt()
        return {'type': 'WHILE', 'children': [cond, body]}

    def parse_expr_stmt():
        left = consume('IDENTIFIER')
        if match('ASSIGN'):
            rhs = parse_expr()
            return {'type': 'ASSIGN',
                    'children': [{'type': 'ID', 'sval': left['val'], 'children': []}, rhs]}
        if peek()['type'] == 'LPAREN':
            pos[0] -= 1
            return parse_call_expr()
        pos[0] -= 1
        return parse_expr()

    def parse_expr():
        return parse_compar()

    def parse_compar():
        left = parse_add_sub()
        ops = {'EQ': '==', 'NEQ': '!=', 'LT': '<', 'GT': '>', 'LE': '<=', 'GE': '>='}
        while peek()['type'] in ops:
            op = ops[peek()['type']]
            pos[0] += 1
            right = parse_add_sub()
            left = {'type': 'BINOP', 'sval': op, 'children': [left, right]}
        return left

    def parse_add_sub():
        left = parse_mul_div()
        while peek()['type'] in ('PLUS', 'MINUS'):
            op = '+' if peek()['type'] == 'PLUS' else '-'
            pos[0] += 1
            left = {'type': 'BINOP', 'sval': op, 'children': [left, parse_mul_div()]}
        return left

    def parse_mul_div():
        left = parse_unary()
        while peek()['type'] in ('MUL', 'DIV'):
            op = '*' if peek()['type'] == 'MUL' else '/'
            pos[0] += 1
            left = {'type': 'BINOP', 'sval': op, 'children': [left, parse_unary()]}
        return left

    def parse_unary():
        if peek()['type'] == 'MINUS':
            pos[0] += 1
            return {'type': 'UNOP', 'sval': '-', 'children': [parse_primary()]}
        return parse_primary()

    def parse_primary():
        t = peek()
        if t['type'] == 'INT_LITERAL':
            pos[0] += 1
            return {'type': 'INT_LIT', 'ival': int(t['val']), 'children': []}
        if t['type'] == 'FLOAT_LITERAL':
            pos[0] += 1
            return {'type': 'FLOAT_LIT', 'fval': float(t['val']), 'children': []}
        if t['type'] == 'STRING_LITERAL':
            pos[0] += 1
            return {'type': 'STRING_LIT', 'sval': t['val'], 'children': []}
        if t['type'] == 'IDENTIFIER':
            next_tok = tokens[pos[0]+1] if pos[0]+1 < len(tokens) else {'type': 'EOF'}
            if next_tok['type'] == 'LPAREN':
                return parse_call_expr()
            pos[0] += 1
            return {'type': 'ID', 'sval': t['val'], 'children': []}
        if t['type'] == 'LPAREN':
            pos[0] += 1
            e = parse_expr()
            consume('RPAREN')
            return e
        raise ParseError(f"Unexpected token: {t['type']} '{t['val']}'")

    def parse_call_expr():
        name = consume('IDENTIFIER')['val']
        consume('LPAREN')
        args = {'type': 'ARG_LIST', 'children': []}
        while peek()['type'] != 'RPAREN':
            args['children'].append(parse_expr())
            if not match('COMMA'):
                break
        consume('RPAREN')
        return {'type': 'CALL', 'sval': name, 'children': [args]}

    return parse_program()


# ── pretty-printer ─────────────────────────────────────────────

def print_ast(node, depth=0, last=True, prefix=''):
    if node is None:
        return
    connector = '└── ' if last else '├── '
    label = f"[{node['type']}]"
    attrs = ''
    if 'sval' in node:
        attrs += f"  name='{node['sval']}'"
    if 'data_type' in node:
        attrs += f"  type='{node['data_type']}'"
    if node['type'] == 'INT_LIT':
        attrs += f"  val={node['ival']}"
    if node['type'] == 'FLOAT_LIT':
        attrs += f"  val={node['fval']}"

    if depth == 0:
        print(label + attrs)
    else:
        print(prefix + connector + label + attrs)

    children = node.get('children', [])
    new_prefix = prefix + ('    ' if last else '│   ')
    for i, child in enumerate(children):
        print_ast(child, depth + 1, i == len(children) - 1, new_prefix)


def print_ast_phase(ast):
    print("=" * 55)
    print("  PHASE 2 — PARSER / ABSTRACT SYNTAX TREE")
    print("=" * 55)
    print_ast(ast)
    print("=" * 55)
