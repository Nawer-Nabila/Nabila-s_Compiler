# ============================================================
# PHASE 5 — THREE ADDRESS CODE (TAC / IR) GENERATOR
# Mini C Compiler
# ============================================================


def generate_tac(ast) -> list[str]:
    code     = []
    counters = {'tmp': 0, 'lbl': 0}

    def new_tmp():
        t = f"t{counters['tmp']}"
        counters['tmp'] += 1
        return t

    def new_label():
        lbl = f"L{counters['lbl']}"
        counters['lbl'] += 1
        return lbl

    def emit(s: str):
        code.append(s)

    # ── statement generator ────────────────────────────────────

    def gen_stmt(node):
        if node is None:
            return
        t = node['type']

        if t in ('PROGRAM', 'BLOCK', 'STMT_LIST'):
            for child in node.get('children', []):
                gen_stmt(child)

        elif t == 'FUNC_DEF':
            emit(f"FUNC_BEGIN {node['sval']}")
            params = node['children'][0].get('children', [])
            for p in params:
                emit(f"  PARAM_DECL {p['data_type']} {p['sval']}")
            for child in node['children'][1:]:
                gen_stmt(child)
            emit(f"FUNC_END {node['sval']}")
            emit('')

        elif t == 'VAR_DECL':
            emit(f"  DECLARE {node['data_type']} {node['sval']}")
            if node.get('children'):
                val = gen_expr(node['children'][0])
                emit(f"  {node['sval']} = {val}")

        elif t == 'ASSIGN':
            lhs = node['children'][0]['sval']
            rhs = gen_expr(node['children'][1])
            emit(f"  {lhs} = {rhs}")

        elif t == 'IF':
            cond   = gen_expr(node['children'][0])
            l_else = new_label()
            l_end  = new_label()
            emit(f"  IF_FALSE {cond} GOTO {l_else}")
            gen_stmt(node['children'][1])
            if len(node['children']) > 2:
                emit(f"  GOTO {l_end}")
                emit(f"{l_else}:")
                gen_stmt(node['children'][2])
                emit(f"{l_end}:")
            else:
                emit(f"{l_else}:")

        elif t == 'WHILE':
            l_start = new_label()
            l_end   = new_label()
            emit(f"{l_start}:")
            cond = gen_expr(node['children'][0])
            emit(f"  IF_FALSE {cond} GOTO {l_end}")
            gen_stmt(node['children'][1])
            emit(f"  GOTO {l_start}")
            emit(f"{l_end}:")

        elif t == 'RETURN':
            if node.get('children'):
                val = gen_expr(node['children'][0])
                emit(f"  RETURN {val}")
            else:
                emit("  RETURN")

        else:
            for child in node.get('children', []):
                gen_stmt(child)

    # ── expression generator ───────────────────────────────────

    def gen_expr(node) -> str:
        if node is None:
            return '?'
        t = node['type']

        if t == 'INT_LIT':
            return str(node['ival'])
        if t == 'FLOAT_LIT':
            return str(node['fval'])
        if t == 'STRING_LIT':
            return node['sval']
        if t == 'ID':
            return node['sval']

        if t == 'BINOP':
            left  = gen_expr(node['children'][0])
            right = gen_expr(node['children'][1])
            tmp   = new_tmp()
            emit(f"  {tmp} = {left} {node['sval']} {right}")
            return tmp

        if t == 'UNOP':
            val = gen_expr(node['children'][0])
            tmp = new_tmp()
            emit(f"  {tmp} = {node['sval']}{val}")
            return tmp

        if t == 'CALL':
            args = node['children'][0].get('children', []) if node['children'] else []
            vals = [gen_expr(a) for a in args]
            for v in vals:
                emit(f"  PARAM {v}")
            tmp = new_tmp()
            emit(f"  {tmp} = CALL {node['sval']}, {len(vals)}")
            return tmp

        return '?'

    gen_stmt(ast)
    return code


# ── printer ────────────────────────────────────────────────────

def print_tac(tac_lines: list[str]):
    non_empty   = [l for l in tac_lines if l.strip()]
    func_count  = sum(1 for l in tac_lines if l.strip().startswith('FUNC_BEGIN'))
    temp_count  = sum(1 for l in tac_lines if 't' in l and '= ' in l
                      and l.strip().split()[0].startswith('t')
                      and l.strip().split()[0][1:].isdigit())

    print("=" * 60)
    print("  PHASE 5 — THREE ADDRESS CODE  (TAC / IR)")
    print("=" * 60)
    print(f"  Instructions : {len(non_empty)}")
    print(f"  Functions    : {func_count}")
    print(f"  Temporaries  : {temp_count}")
    print("-" * 60)

    line_num = 0
    for raw in tac_lines:
        stripped = raw.strip()
        if not stripped:
            print()
            continue
        line_num += 1
        print(f"  {line_num:>3}   {raw}")

    print("=" * 60)
