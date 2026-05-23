"""
grammar_tool.py  –  CLI interface for LL(1) grammar transformations.
Run:  python grammar_tool.py
"""

from grammar_utils import remove_left_recursion, left_factoring, print_grammar


def tokenize_production(prod_str: str) -> list:
    """
    Split a production string into individual grammar symbols.
    
    Handles two formats:
      1. Space-separated:   'i E t S e S'  →  ['i', 'E', 't', 'S', 'e', 'S']
      2. Compact (no spaces): 'iEtSeS'     →  ['i', 'E', 't', 'S', 'e', 'S']
         - Uppercase letter = non-terminal (own token)
         - Lowercase letter = terminal (own token)
         - ε stays as-is
    """
    prod_str = prod_str.strip()
    if prod_str == 'ε' or prod_str == 'eps' or prod_str == "''":
        return ['ε']

    # If it contains spaces, trust the spacing
    if ' ' in prod_str:
        return prod_str.split()

    # Compact format: split into individual characters
    # Each character is its own symbol
    tokens = []
    i = 0
    while i < len(prod_str):
        ch = prod_str[i]
        if ch == 'ε':
            tokens.append('ε')
        else:
            tokens.append(ch)
        i += 1
    return tokens


def input_grammar() -> dict:
    grammar = {}
    print()
    print("  Tip: you can write productions compactly  (e.g.  S -> iEtS | iEtSeS | a)")
    print("       or space-separated                   (e.g.  S -> i E t S | i E t S e S | a)")
    print()
    n = int(input("Number of productions: "))
    for _ in range(n):
        line = input("Enter production (e.g.  S -> iEtS | iEtSeS | a): ")
        if '->' not in line:
            print("  !! Skipping — no '->' found")
            continue
        left, right = line.split('->', 1)
        left = left.strip()
        grammar[left] = [tokenize_production(prod) for prod in right.strip().split('|')]
    return grammar


if __name__ == "__main__":
    grammar = input_grammar()

    print("\n── Original Grammar ──────────────────────")
    print_grammar(grammar)

    grammar = remove_left_recursion(grammar)
    print("\n── After Removing Left Recursion ─────────")
    print_grammar(grammar)

    grammar = left_factoring(grammar)
    print("\n── After Left Factoring ──────────────────")
    print_grammar(grammar)