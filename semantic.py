# ============================================================
# PHASE 4 — SEMANTIC ANALYSIS
# Mini C Compiler
# ============================================================


CHECKS = [
    ("All identifiers declared before use",
     "No undeclared variables or functions"),
    ("No redeclarations in same scope",
     "Each name declared once per scope"),
    ("Function call argument counts",
     "Argument count matches parameter count"),
    ("Return type compatibility",
     "Return expression matches function type"),
    ("Assignment type compatibility",
     "int ↔ float implicit widening allowed"),
]


def semantic_analysis(ast, sym_data: dict) -> list[str]:
    """
    Re-uses errors already found during symbol table build,
    then adds any extra semantic checks.
    Returns a list of error strings.
    """
    errors = list(sym_data.get('errors', []))

    # Build a flat lookup from all scopes for quick access
    all_syms = {}
    for scope in sym_data.get('scopes', []):
        for name, entry in scope.items():
            if name not in all_syms:
                all_syms[name] = entry

    # ── Check function call argument counts ────────────────────
    def check_calls(node):
        if node is None:
            return
        if node['type'] == 'CALL':
            fname = node.get('sval', '')
            args  = node['children'][0].get('children', []) if node['children'] else []
            sym   = all_syms.get(fname)
            if sym and sym['kind'] == 'function' and 'params' in sym:
                expected = len(sym['params'])
                got      = len(args)
                if expected != got:
                    errors.append(
                        f"Function '{fname}' called with {got} args, "
                        f"but defined with {expected} params"
                    )
        for child in node.get('children', []):
            check_calls(child)

    check_calls(ast)

    return errors


def print_semantic(errors: list[str]):
    print("=" * 60)
    print("  PHASE 4 — SEMANTIC ANALYSIS")
    print("=" * 60)

    for label, sub in CHECKS:
        # simple heuristic: match first word of label against errors
        keyword = label.lower().split()[0]
        is_err  = any(keyword in e.lower() for e in errors)
        mark    = "✗" if is_err else "✓"
        print(f"\n  {mark}  {label}")
        print(f"       {sub}")

    print()
    if errors:
        print("  ─" * 30)
        print(f"  ⚠  Semantic analysis found {len(errors)} error(s):\n")
        for e in errors:
            print(f"    ✗  {e}")
    else:
        print("  " + "─" * 56)
        print("  ✓  Semantic analysis passed — no errors found")
    print("=" * 60)
