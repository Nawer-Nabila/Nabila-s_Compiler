# ============================================================
# PHASE 3 — SYMBOL TABLE BUILDER
# Mini C Compiler
# ============================================================


def build_symbol_table(ast) -> dict:
    """
    Returns:
        {
          'scopes': [ {name: symbol_entry, ...}, ... ],
          'errors': [ str, ... ]
        }
    symbol_entry keys: name, type, kind, scope, addr, initialized
    """
    scopes_stack = [{}]          # stack of active scopes
    all_scopes   = [scopes_stack[0]]  # every scope ever created (for printing)
    errors       = []
    addr_stack   = [0x1000]      # local frame offset per scope level
    WORD = 4

    def enter_scope():
        new_scope = {}
        scopes_stack.append(new_scope)
        all_scopes.append(new_scope)
        # local stack frame starts just below previous
        addr_stack.append(0xBF00 - (len(scopes_stack) - 1) * 0x100)

    def exit_scope():
        scopes_stack.pop()
        addr_stack.pop()

    def declare(name, typ, kind='variable', initialized=False, is_func=False, params=None):
        cur = scopes_stack[-1]
        if name in cur:
            errors.append(f"Redeclaration of '{name}' in same scope")
            return
        if is_func:
            addr = 0
        else:
            addr = addr_stack[-1]
            size = 4 if typ in ('int', 'float') else 1 if typ == 'char' else 0
            addr_stack[-1] += size

        entry = {
            'name':        name,
            'type':        typ,
            'kind':        kind,
            'scope':       len(scopes_stack) - 1,
            'addr':        addr,
            'initialized': initialized,
        }
        if params is not None:
            entry['params'] = params
        cur[name] = entry

    def lookup(name):
        for scope in reversed(scopes_stack):
            if name in scope:
                return scope[name]
        return None

    def require(name):
        if lookup(name) is None:
            errors.append(f"Use of undeclared identifier '{name}'")

    # ── tree walk ──────────────────────────────────────────────

    def walk(node):
        if node is None:
            return
        t = node['type']

        if t in ('PROGRAM', 'BLOCK', 'STMT_LIST'):
            for child in node.get('children', []):
                walk(child)

        elif t == 'FUNC_DEF':
            param_types = [p['data_type'] for p in node['children'][0].get('children', [])]
            declare(node['sval'], node['data_type'], kind='function',
                    initialized=True, is_func=True, params=param_types)
            enter_scope()
            for param in node['children'][0].get('children', []):
                declare(param['sval'], param['data_type'], kind='param', initialized=True)
            for child in node['children'][1:]:
                walk(child)
            exit_scope()

        elif t == 'VAR_DECL':
            initialized = len(node.get('children', [])) > 0
            declare(node['sval'], node['data_type'], kind='variable',
                    initialized=initialized)
            for child in node.get('children', []):
                walk(child)

        elif t == 'ASSIGN':
            lhs_name = node['children'][0].get('sval')
            if lhs_name:
                entry = lookup(lhs_name)
                if entry:
                    entry['initialized'] = True
                else:
                    errors.append(f"Use of undeclared identifier '{lhs_name}'")
            walk(node['children'][1])

        elif t == 'ID':
            require(node['sval'])

        elif t == 'CALL':
            require(node['sval'])
            for child in node.get('children', []):
                walk(child)

        else:
            for child in node.get('children', []):
                walk(child)

    walk(ast)
    return {'scopes': all_scopes, 'errors': errors}


# ── printer ────────────────────────────────────────────────────

def print_symbol_table(sym_data: dict):
    scopes = sym_data['scopes']
    errors = sym_data['errors']

    total = sum(len(s) for s in scopes)
    funcs = sum(1 for s in scopes for e in s.values() if e['kind'] == 'function')
    vars_ = total - funcs

    print("=" * 70)
    print("  PHASE 3 — SYMBOL TABLE")
    print("=" * 70)
    print(f"  Total Symbols : {total}   Functions : {funcs}   Variables : {vars_}")
    if errors:
        print(f"  ERRORS        : {len(errors)}")
    print("-" * 70)

    for level, scope in enumerate(scopes):
        if not scope:
            continue
        scope_label = "Global scope" if level == 0 else f"Local scope (level {level})"
        print(f"\n  [{scope_label}]")
        print(f"  {'Name':<14} {'Type':<8} {'Kind':<10} {'Scope':<7} {'Address':<10} {'Size':<6} {'Init'}")
        print("  " + "-" * 60)
        for sym in scope.values():
            addr_str = "—" if sym['kind'] == 'function' else f"0x{sym['addr']:04X}"
            size_str = ("—" if sym['kind'] == 'function'
                        else "4" if sym['type'] in ('int', 'float')
                        else "1" if sym['type'] == 'char' else "0")
            init_str = ("—" if sym['kind'] == 'function'
                        else "yes" if sym['initialized'] else "no")
            print(f"  {sym['name']:<14} {sym['type']:<8} {sym['kind']:<10} "
                  f"{sym['scope']:<7} {addr_str:<10} {size_str:<6} {init_str}")

    print()
    if errors:
        print("  ERRORS:")
        for e in errors:
            print(f"    ✗  {e}")
    else:
        print("  ✓  No symbol-table errors")
    print("=" * 70)
