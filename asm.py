# ============================================================
# PHASE 6 — x86 ASSEMBLY GENERATOR  (Intel syntax, 32-bit)
# Mini C Compiler
# ============================================================

import re

WORD = 4   # bytes per int/pointer


def generate_asm(tac: list[str]) -> list[str]:
    asm      = []
    frame    = {}          # var_name -> frame offset from bp
    frame_sz = [0]         # mutable int
    cur_fn   = [None]

    def alloc(name: str):
        if name not in frame:
            frame_sz[0] += WORD
            frame[name]  = frame_sz[0]

    def operand(v: str) -> str:
        """Translate a TAC value to an assembly operand."""
        try:
            float(v)       # numeric literal
            return str(int(float(v))) if '.' not in v else v
        except (ValueError, TypeError):
            pass
        if v in frame:
            return f"[bp-{frame[v]}]"
        return v

    def emit(s: str):
        asm.append(s)

    # PLACEHOLDER tag so we can back-patch frame size after we know it
    FS_TAG = lambda fn: f"<FS_{fn}>"

    for raw in tac:
        line = raw.strip()

        # ── blank line ─────────────────────────────────────────
        if not line:
            emit('')
            continue

        # ── FUNC_BEGIN ─────────────────────────────────────────
        if line.startswith('FUNC_BEGIN'):
            fn = line.split()[1]
            cur_fn[0] = fn
            frame.clear()
            frame_sz[0] = 0
            emit(f"{fn}:")
            emit(f"    push  bp")
            emit(f"    mov   bp, sp")
            emit(f"    sub   sp, {FS_TAG(fn)}")

        # ── FUNC_END ───────────────────────────────────────────
        elif line.startswith('FUNC_END'):
            fn  = line.split()[1]
            fs  = frame_sz[0]
            emit(f".{fn}_ret:")
            emit(f"    mov   sp, bp")
            emit(f"    pop   bp")
            emit(f"    ret")
            emit(f"; ---- end {fn}  (frame = {fs} bytes) ----")
            emit('')
            # back-patch frame-size placeholder
            tag = FS_TAG(fn)
            for i, l in enumerate(asm):
                if tag in l:
                    asm[i] = l.replace(tag, str(fs))
            cur_fn[0] = None

        # ── DECLARE / PARAM_DECL ───────────────────────────────
        elif line.startswith('DECLARE') or line.startswith('PARAM_DECL'):
            parts = line.split()
            name  = parts[2]
            alloc(name)
            emit(f"    ; {name} -> [bp-{frame[name]}]")

        # ── RETURN ─────────────────────────────────────────────
        elif line.startswith('RETURN'):
            parts = line.split()
            val   = parts[1] if len(parts) > 1 else None
            if val:
                src = operand(val)
                emit(f"    mov   eax, {src}")
            else:
                emit(f"    mov   eax, 0")
            emit(f"    jmp   .{cur_fn[0]}_ret")

        # ── IF_FALSE cond GOTO label ───────────────────────────
        elif line.startswith('IF_FALSE'):
            parts = line.split()
            cond  = operand(parts[1])
            label = parts[3]
            emit(f"    mov   eax, {cond}")
            emit(f"    cmp   eax, 0")
            emit(f"    je    {label}")

        # ── GOTO label ─────────────────────────────────────────
        elif line.startswith('GOTO'):
            emit(f"    jmp   {line.split()[1]}")

        # ── PARAM val ──────────────────────────────────────────
        elif line.startswith('PARAM '):
            val = line.split(None, 1)[1]
            src = operand(val)
            try:
                float(src)
                emit(f"    push  {src}")
            except (ValueError, TypeError):
                emit(f"    mov   eax, {src}")
                emit(f"    push  eax")

        # ── label: ─────────────────────────────────────────────
        elif re.match(r'^[A-Za-z_][A-Za-z0-9_]*:$', line) or \
             re.match(r'^\.[A-Za-z_][A-Za-z0-9_.]*:$', line):
            emit(line)

        # ── dest = CALL fn, argc ────────────────────────────────
        elif '= CALL' in line:
            dest, rhs = [s.strip() for s in line.split('=', 1)]
            parts     = re.split(r'[\s,]+', rhs)
            fn        = parts[1]
            argc      = int(parts[2]) if len(parts) > 2 else 0
            alloc(dest)
            emit(f"    call  {fn}")
            if argc:
                emit(f"    add   sp, {argc * WORD}")
            emit(f"    mov   {operand(dest)}, eax")

        # ── dest = expr ─────────────────────────────────────────
        elif '=' in line:
            dest, rhs = [s.strip() for s in line.split('=', 1)]
            alloc(dest)

            # Try binary operator  (search right-to-left for correct precedence)
            BIN_OPS = ['==', '!=', '<=', '>=', '<', '>', '+', '-', '*', '/']
            found = None
            for bop in BIN_OPS:
                pat = r' ' + re.escape(bop) + r' '
                idx = rhs.rfind(' ' + bop + ' ')
                if idx >= 0:
                    found = {
                        'op': bop,
                        'l':  rhs[:idx].strip(),
                        'r':  rhs[idx + len(bop) + 2:].strip()   # after ' op '
                    }
                    break

            if found:
                emit(f"    mov   eax, {operand(found['l'])}")
                right = operand(found['r'])
                op    = found['op']

                if op == '+':
                    try:
                        float(right); emit(f"    add   eax, {right}")
                    except (ValueError, TypeError):
                        emit(f"    mov   ebx, {right}"); emit(f"    add   eax, ebx")
                elif op == '-':
                    try:
                        float(right); emit(f"    sub   eax, {right}")
                    except (ValueError, TypeError):
                        emit(f"    mov   ebx, {right}"); emit(f"    sub   eax, ebx")
                elif op == '*':
                    emit(f"    mov   ebx, {right}")
                    emit(f"    imul  eax, ebx")
                elif op == '/':
                    emit(f"    cdq")
                    emit(f"    mov   ebx, {right}")
                    emit(f"    idiv  ebx")
                else:
                    SET_MAP = {
                        '==': 'sete', '!=': 'setne',
                        '<':  'setl', '>':  'setg',
                        '<=': 'setle', '>=': 'setge'
                    }
                    emit(f"    mov   ebx, {right}")
                    emit(f"    cmp   eax, ebx")
                    emit(f"    {SET_MAP[op]}  al")
                    emit(f"    movzx eax, al")

                emit(f"    mov   {operand(dest)}, eax")

            else:
                src = operand(rhs)
                emit(f"    mov   eax, {src}")
                emit(f"    mov   {operand(dest)}, eax")

    return asm


# ── printer ────────────────────────────────────────────────────

def print_asm(asm_lines: list[str]):
    instr_count = sum(
        1 for l in asm_lines
        if l.strip() and not l.strip().startswith(';')
        and not re.match(r'^[A-Za-z_.][A-Za-z0-9_.]*:$', l.strip())
    )

    print("=" * 60)
    print("  PHASE 6 — x86 ASSEMBLY  (Intel syntax, 32-bit)")
    print("=" * 60)
    print(f"  Instructions (non-label, non-comment): {instr_count}")
    print("-" * 60)

    for i, raw in enumerate(asm_lines, 1):
        stripped = raw.strip()
        if not stripped:
            print()
            continue
        if stripped.startswith(';'):
            print(f"  {i:>4}   {raw}")          # comment
        elif re.match(r'^\.?[A-Za-z_][A-Za-z0-9_.]*:$', stripped):
            print(f"\n  {i:>4} {raw}")           # label on its own line
        else:
            print(f"  {i:>4}   {raw}")

    print("=" * 60)
