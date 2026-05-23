"""
grammar_utils.py  –  LL(1) grammar analysis utilities.
Fixed bugs:
  • compute_first: correctly handles all epsilon-derivable chains
  • compute_follow: correctly propagates through nullable suffixes
  • format_* helpers unchanged
"""

import re
from collections import OrderedDict


# ─────────────────────────────────────────────────────────────────────────────
#  Normalizer
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_grammar(grammar: dict) -> dict:
    """
    Ensure every token in every production is a single symbol:
      - known NT  → kept as-is
      - 'ε'       → kept as-is
      - len==1    → kept as-is (single-char terminal or NT)
      - all-lowercase/digit multi-char (e.g. 'id', 'num') → kept as-is (multi-char terminal)
      - otherwise → split character by character
    """
    nts = set(grammar.keys())

    def split_prod(prod):
        result = []
        for token in prod:
            if token == 'ε':
                result.append(token)
            elif token in nts or len(token) == 1:
                result.append(token)
            elif re.match(r'^[a-z0-9_]+$', token):
                # multi-char lowercase terminal (e.g. 'id', 'then', 'num') — keep whole
                result.append(token)
            else:
                # mixed-case compact string — split char by char,
                # but first try to consume known NTs greedily
                i = 0
                while i < len(token):
                    matched = False
                    for length in range(len(token) - i, 1, -1):
                        if token[i:i+length] in nts:
                            result.append(token[i:i+length])
                            i += length
                            matched = True
                            break
                    if not matched:
                        result.append(token[i])
                        i += 1
        return result

    new_grammar = OrderedDict()
    for nt, productions in grammar.items():
        new_grammar[nt] = [split_prod(p) for p in productions]
    return new_grammar


# ─────────────────────────────────────────────────────────────────────────────
#  Left Recursion Removal  (direct + indirect)
# ─────────────────────────────────────────────────────────────────────────────

def remove_left_recursion(grammar: dict) -> dict:
    """Remove both direct AND indirect left recursion."""
    grammar     = _normalize_grammar(grammar)
    nts         = list(grammar.keys())
    new_grammar = OrderedDict((nt, list(prods)) for nt, prods in grammar.items())

    for i, ai in enumerate(nts):
        # Substitute earlier NTs to expose indirect left recursion
        for aj in nts[:i]:
            new_prods = []
            for prod in new_grammar[ai]:
                if prod and prod[0] == aj:
                    for aj_prod in new_grammar[aj]:
                        if aj_prod == ['ε']:
                            new_prods.append(prod[1:] if prod[1:] else ['ε'])
                        else:
                            new_prods.append(aj_prod + prod[1:])
                else:
                    new_prods.append(prod)
            new_grammar[ai] = new_prods

        # Now eliminate direct left recursion for ai
        recursive     = []
        non_recursive = []
        for prod in new_grammar[ai]:
            if prod and prod[0] == ai:
                recursive.append(prod[1:])
            else:
                non_recursive.append(prod)

        if not recursive:
            continue

        prime = ai + "'"
        while prime in new_grammar:
            prime += "'"

        new_grammar[ai] = []
        for beta in non_recursive:
            new_grammar[ai].append((beta if beta else ['ε']) + [prime])
        if not non_recursive:
            new_grammar[ai].append([prime])

        new_grammar[prime] = []
        for alpha in recursive:
            new_grammar[prime].append((alpha if alpha else ['ε']) + [prime])
        new_grammar[prime].append(['ε'])

    return new_grammar


# ─────────────────────────────────────────────────────────────────────────────
#  Left Factoring
# ─────────────────────────────────────────────────────────────────────────────

def _common_prefix(prods: list) -> list:
    if not prods:
        return []
    prefix = list(prods[0])
    for prod in prods[1:]:
        length = 0
        for a, b in zip(prefix, prod):
            if a == b:
                length += 1
            else:
                break
        prefix = prefix[:length]
        if not prefix:
            break
    return prefix


def left_factoring(grammar: dict) -> dict:
    """Apply left factoring using longest-common-prefix grouping."""
    grammar = _normalize_grammar(grammar)

    def _make_new_nt(base: str, existing: set) -> str:
        candidate = base + "'"
        while candidate in existing:
            candidate += "'"
        return candidate

    changed = True
    while changed:
        changed = False
        new_grammar = OrderedDict()

        for nt, productions in grammar.items():
            all_nts = set(grammar.keys()) | set(new_grammar.keys())

            groups: dict = OrderedDict()
            for prod in productions:
                key = prod[0] if prod else 'ε'
                groups.setdefault(key, []).append(prod)

            if all(len(g) == 1 for g in groups.values()):
                new_grammar[nt] = productions
                continue

            changed = True
            new_grammar[nt] = []

            for _key, group in groups.items():
                if len(group) == 1:
                    new_grammar[nt].append(group[0])
                    continue

                lcp    = _common_prefix(group)
                new_nt = _make_new_nt(nt, all_nts)
                all_nts.add(new_nt)

                new_grammar[nt].append(lcp + [new_nt])
                new_grammar[new_nt] = []
                for prod in group:
                    rest = prod[len(lcp):]
                    new_grammar[new_nt].append(rest if rest else ['ε'])

        grammar = new_grammar

    return grammar


# ─────────────────────────────────────────────────────────────────────────────
#  FIRST Sets
# ─────────────────────────────────────────────────────────────────────────────

def compute_first(grammar: dict) -> dict:
    """
    Compute FIRST sets for all non-terminals.
    A terminal t is in FIRST(A) if A =>* t...
    ε is in FIRST(A) if A =>* ε
    """
    first = {nt: set() for nt in grammar}

    def first_of(symbol):
        """FIRST of a single symbol (NT or terminal)."""
        if symbol not in grammar:
            return {symbol}          # terminal → {terminal}
        return first[symbol]         # NT → current approximation

    changed = True
    while changed:
        changed = False
        for nt, productions in grammar.items():
            for prod in productions:
                # Empty production (explicit epsilon)
                if prod == ['ε']:
                    if 'ε' not in first[nt]:
                        first[nt].add('ε')
                        changed = True
                    continue

                # Walk symbols; break as soon as one can't derive ε
                derives_eps = True
                for symbol in prod:
                    f      = first_of(symbol)
                    before = len(first[nt])
                    first[nt] |= (f - {'ε'})
                    if len(first[nt]) != before:
                        changed = True
                    if 'ε' not in f:
                        derives_eps = False
                        break

                # All symbols derive ε → whole production derives ε
                if derives_eps:
                    if 'ε' not in first[nt]:
                        first[nt].add('ε')
                        changed = True

    return first


# ─────────────────────────────────────────────────────────────────────────────
#  FOLLOW Sets
# ─────────────────────────────────────────────────────────────────────────────

def compute_follow(grammar: dict, first: dict) -> dict:
    """
    Compute FOLLOW sets for all non-terminals.
    
    Rules:
      1. $ ∈ FOLLOW(start)
      2. If A → α B β: FIRST(β) - {ε} ⊆ FOLLOW(B)
      3. If A → α B β and ε ∈ FIRST(β): FOLLOW(A) ⊆ FOLLOW(B)
      4. If A → α B: FOLLOW(A) ⊆ FOLLOW(B)
    """
    nts    = list(grammar.keys())
    follow = {nt: set() for nt in nts}
    follow[nts[0]].add('$')

    def first_of_sequence(symbols):
        """
        Returns (first_set_without_eps, all_nullable) for a sequence of symbols.
        all_nullable=True means the entire sequence can derive ε.
        """
        result     = set()
        all_nullable = True
        for s in symbols:
            sf = first.get(s, set()) if s in grammar else {s}
            result |= (sf - {'ε'})
            if 'ε' not in sf:
                all_nullable = False
                break
        return result, all_nullable

    changed = True
    while changed:
        changed = False
        for nt, productions in grammar.items():
            for prod in productions:
                if prod == ['ε']:
                    continue
                for idx, symbol in enumerate(prod):
                    if symbol not in grammar:
                        continue   # only compute FOLLOW for non-terminals

                    rest                = prod[idx + 1:]
                    first_rest, all_eps = first_of_sequence(rest)

                    before = len(follow[symbol])

                    # Rule 2: add FIRST(rest) - {ε}
                    follow[symbol] |= first_rest

                    # Rule 3 & 4: if rest =>* ε, add FOLLOW(nt)
                    if all_eps:
                        follow[symbol] |= follow[nt]

                    if len(follow[symbol]) != before:
                        changed = True

    return follow


# ─────────────────────────────────────────────────────────────────────────────
#  Parsing Table
# ─────────────────────────────────────────────────────────────────────────────

def compute_parsing_table(grammar: dict, first: dict, follow: dict) -> dict:
    """Build the LL(1) predictive parsing table."""
    table = {}

    def first_of_prod(prod):
        """Compute FIRST of a production (list of symbols)."""
        if prod == ['ε']:
            return {'ε'}
        result    = set()
        all_nullable = True
        for symbol in prod:
            sf = first.get(symbol, {symbol}) if symbol in grammar else {symbol}
            result |= (sf - {'ε'})
            if 'ε' not in sf:
                all_nullable = False
                break
        if all_nullable:
            result.add('ε')
        return result

    for nt, productions in grammar.items():
        for prod in productions:
            fp = first_of_prod(prod)

            # For each terminal in FIRST(prod), add to table
            for terminal in fp - {'ε'}:
                table.setdefault((nt, terminal), []).append(prod)

            # If ε ∈ FIRST(prod), add prod for each terminal in FOLLOW(nt)
            if 'ε' in fp:
                for terminal in follow.get(nt, set()):
                    table.setdefault((nt, terminal), []).append(prod)

    return table


# ─────────────────────────────────────────────────────────────────────────────
#  Display Helpers
# ─────────────────────────────────────────────────────────────────────────────

def format_grammar(grammar: dict, title: str = '') -> str:
    lines = []
    if title:
        lines.append(title)
        lines.append('─' * max(len(title), 40))
    for nt, productions in grammar.items():
        rhs = ' | '.join(' '.join(prod) for prod in productions)
        lines.append(f'  {nt:<12} →  {rhs}')
    return '\n'.join(lines)


def format_first_follow(first: dict, follow: dict) -> str:
    lines = ['── FIRST Sets ─────────────────────────', '']
    for nt, s in first.items():
        clean = ', '.join(sorted(s)) if s else '∅'
        lines.append(f'  FIRST({nt}) = {{ {clean} }}')
    lines += ['', '── FOLLOW Sets ────────────────────────', '']
    for nt, s in follow.items():
        if not s:
            lines.append(f'  FOLLOW({nt}) = ∅')
        else:
            clean = ', '.join(sorted(s))
            lines.append(f'  FOLLOW({nt}) = {{ {clean} }}')
    return '\n'.join(lines)


def format_parsing_table(grammar: dict, table: dict, follow: dict) -> str:
    nts       = list(grammar.keys())
    terminals = sorted({t for (_, t) in table.keys()})

    if not terminals:
        return '── LL(1) Parsing Table ────────────────\n\n  (no terminals found)'

    def cell_str(nt, t):
        cell = table.get((nt, t), [])
        if not cell:        return ''
        if len(cell) == 1:  return f"{nt} → {' '.join(cell[0])}"
        return '⚠ CONFLICT'

    nt_w  = max(len(nt) for nt in nts) + 2
    col_w = max(
        max(len(t) for t in terminals),
        max(
            len(cell_str(nt, t))
            for nt in nts
            for t in terminals
        ),
        8
    ) + 4

    def hline(l, m, r):
        return l + '─' * (nt_w + 2) + m + m.join('─' * (col_w + 2) for _ in terminals) + r

    lines = ['── LL(1) Parsing Table ────────────────', '']

    lines.append(hline('┌', '┬', '┐'))

    hdr = '│' + f"{'':^{nt_w + 2}}" + '│'
    for t in terminals:
        hdr += f" {t:^{col_w}} │"
    lines.append(hdr)

    lines.append(hline('├', '┼', '┤'))

    has_conflict = False
    for idx, nt in enumerate(nts):
        row = '│' + f" {nt:^{nt_w}} " + '│'
        for t in terminals:
            val = cell_str(nt, t)
            if '⚠' in val:
                has_conflict = True
            row += f" {val:^{col_w}} │"
        lines.append(row)
        if idx < len(nts) - 1:
            lines.append(hline('├', '┼', '┤'))

    lines.append(hline('└', '┴', '┘'))
    lines.append('')
    lines.append('  ⚠  Grammar is NOT LL(1) — conflicts detected'
                 if has_conflict else '  ✓  Grammar is LL(1)')
    return '\n'.join(lines)


def print_grammar(grammar: dict):
    for nt, productions in grammar.items():
        rhs = ' | '.join(' '.join(prod) for prod in productions)
        print(f'  {nt} → {rhs}')