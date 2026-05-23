#!/usr/bin/env python3
"""
Mini C Compiler — GUI
Pixel-faithful Python port of the HTML/JS compiler UI.
Additions:
  • Resizable editor (no fixed 420 px cap)
  • LL(1) Grammar Analyzer window (Left Recursion, Left Factoring, FIRST/FOLLOW)
    — Parsing Table tab removed
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets  import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                               QVBoxLayout, QSplitter, QPushButton, QLabel,
                               QFrame, QShortcut, QSizePolicy, QDialog,
                               QTextEdit, QLineEdit, QFormLayout, QSpinBox,
                               QScrollArea, QTabWidget, QGroupBox, QMessageBox,
                               QPlainTextEdit, QToolButton, QCheckBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel  import QWebChannel
from PyQt5.QtCore        import Qt, QTimer, QObject, pyqtSlot, QUrl, QSize
from PyQt5.QtGui         import QColor, QPalette, QFont, QKeySequence, QIcon

from lexer        import lex
from parser       import parse, ParseError
from symbol_table import build_symbol_table
from semantic     import semantic_analysis
from tac          import generate_tac
from asm          import generate_asm

from grammar_utils import (remove_left_recursion, left_factoring,
                            compute_first, compute_follow,
                            compute_parsing_table,
                            format_grammar, format_first_follow,
                            format_parsing_table)

# ─── colour tokens ────────────────────────────────────────────
BG="#282A36"; BG2="#21222C"; BG3="#343746"; BORDER="#44475A"
ACCENT="#8BE9FD"; ACCENT2="#BD93F9"; GREEN="#50FA7B"
YELLOW="#F1FA8C"; RED="#FF5555"; TEXT="#F8F8F2"; MUTED="#6272A4"
ORANGE="#FFB86C"; PINK="#FF79C6"

SAMPLES = {
    "simple": "int main() {\n    int x, y;\n    int z;\n    z = x + y;\n    return 0;\n}",
    "arith":  "int main() {\n    int a;\n    int b;\n    int result;\n    a = 10;\n    b = 5;\n    result = a + b;\n    result = a - b;\n    result = a * b;\n    return result;\n}",
    "if":     "int main() {\n    int x;\n    int y;\n    x = 10;\n    if (x > 5) {\n        y = x + 1;\n    } else {\n        y = 0;\n    }\n    return y;\n}",
    "while":  "int main() {\n    int i;\n    int sum;\n    i = 0;\n    sum = 0;\n    while (i < 5) {\n        sum = sum + i;\n        i = i + 1;\n    }\n    return sum;\n}",
    "func":   "int add(int a, int b) {\n    return a + b;\n}\n\nint main() {\n    int x;\n    int y;\n    int result;\n    x = 3;\n    y = 7;\n    result = add(x, y);\n    return result;\n}",
}

# ══════════════════════════════════════════════════════════════
#  Compiler helpers
# ══════════════════════════════════════════════════════════════
def _h(s):
    return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _j(s):
    return str(s or "").replace("\\","\\\\").replace("`","\\`").replace("$","\\$")

def compile_all(src):
    tokens = lex(src)
    ast = None; parse_error = None
    try:    ast = parse(tokens)
    except Exception as e: parse_error = str(e)
    sym  = build_symbol_table(ast)  if ast else {"scopes":[],"errors":[]}
    errs = semantic_analysis(ast,sym) if ast else sym["errors"][:]
    all_errors = (([parse_error] if parse_error else []) + sym["errors"] + errs)
    tac  = generate_tac(ast) if ast else []
    asm  = generate_asm(tac) if tac else []
    return dict(tokens=tokens, ast=ast, parse_error=parse_error,
                symbols=sym, errors=all_errors, tac=tac, asm=asm)

# ── render helpers ─────────────────────────────────────────────
def render_tokens(tokens):
    KW  = {'INT','FLOAT','VOID','RETURN','IF','ELSE','WHILE','CHAR'}
    LIT = {'INT_LITERAL','FLOAT_LITERAL','STRING_LITERAL'}
    OP  = {'PLUS','MINUS','MUL','DIV','ASSIGN','EQ','NEQ','LT','GT','LE','GE'}
    PNC = {'LPAREN','RPAREN','LBRACE','RBRACE','SEMICOLON','COMMA'}
    def cls(t):
        if t in KW:  return "tok-kw"
        if t=="IDENTIFIER": return "tok-id"
        if t in LIT: return "tok-lit"
        if t in OP:  return "tok-op"
        if t in PNC: return "tok-punc"
        return ""
    kw_n = sum(1 for t in tokens if t["type"] in KW)
    id_n = sum(1 for t in tokens if t["type"]=="IDENTIFIER")
    rows = "".join(
        f'<tr><td style="color:var(--muted)">{i+1}</td>'
        f'<td class="tok-type {cls(t["type"])}">{_h(t["type"])}</td>'
        f'<td class="{cls(t["type"])}">{_h(t["val"])}</td></tr>'
        for i,t in enumerate(tokens)
    )
    return f"""
<div class="summary-grid">
  <div class="summary-card"><div class="summary-num">{len(tokens)}</div><div class="summary-label">Total Tokens</div></div>
  <div class="summary-card"><div class="summary-num">{kw_n}</div><div class="summary-label">Keywords</div></div>
  <div class="summary-card"><div class="summary-num">{id_n}</div><div class="summary-label">Identifiers</div></div>
</div>
<div class="output-block">
  <div class="output-block-header">Token Stream <span class="badge">{len(tokens)} tokens</span></div>
  <table class="token-table">
    <thead><tr><th>#</th><th>Type</th><th>Value</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

def render_ast(ast, parse_error):
    if not ast:
        return f'<div class="error-box">Parse failed: {_h(parse_error)}</div>'
    def node_html(node, depth):
        if not node: return ""
        indent = "  " * depth
        conn   = "└─ " if depth > 0 else ""
        attrs  = ""
        if "sval"      in node: attrs += f' <span class="ast-attr-name">name=</span><span class="ast-attr-val">\'{_h(node["sval"])}\'</span>'
        if "data_type" in node: attrs += f' <span class="ast-attr-name">type=</span><span class="ast-attr-val">\'{_h(node["data_type"])}\'</span>'
        if node["type"]=="INT_LIT":   attrs += f' <span class="ast-attr-name">val=</span><span class="ast-attr-val">{node["ival"]}</span>'
        if node["type"]=="FLOAT_LIT": attrs += f' <span class="ast-attr-name">val=</span><span class="ast-attr-val">{node["fval"]}</span>'
        out = f'<div class="ast-node"><span class="ast-connector">{_h(indent+conn)}</span><span class="ast-type">[{_h(node["type"])}]</span>{attrs}</div>'
        for c in (node.get("children") or []):
            out += node_html(c, depth+1)
        return out
    return f"""
<div class="output-block">
  <div class="output-block-header">Abstract Syntax Tree <span class="badge">parsed</span></div>
  <div class="output-pre ast-tree">{node_html(ast,0)}</div>
</div>"""

def render_sym(sym):
    scopes, errors = sym["scopes"], sym["errors"]
    total = sum(len(s) for s in scopes)
    funcs = sum(1 for s in scopes for e in s.values() if e["kind"]=="function")
    vars_ = total - funcs
    err_html = ("".join(f'<div class="error-box">{_h(e)}</div>' for e in errors)) if errors else ""
    rows = ""
    for level, scope in enumerate(scopes):
        entries = list(scope.values())
        if not entries: continue
        lbl = "Global scope" if level==0 else f"Local scope (level {level})"
        rows += f'<tr><td colspan="7" class="scope-label">{lbl}</td></tr>'
        for sym_e in entries:
            kc = ("kind-func" if sym_e["kind"]=="function"
                  else "kind-param" if sym_e["kind"]=="param" else "kind-var")
            addr = "—" if sym_e["kind"]=="function" else f'0x{sym_e["addr"]:04X}'
            sz   = ("—" if sym_e["kind"]=="function"
                    else "4" if sym_e["type"] in ("int","float")
                    else "1" if sym_e["type"]=="char" else "0")
            init = ("—" if sym_e["kind"]=="function"
                    else '<span class="init-yes">yes</span>' if sym_e.get("initialized")
                    else '<span class="init-no">no</span>')
            rows += (f'<tr><td style="color:var(--text);font-weight:500">{_h(sym_e["name"])}</td>'
                     f'<td>{_h(sym_e["type"])}</td><td class="{kc}">{sym_e["kind"]}</td>'
                     f'<td style="text-align:center">{sym_e["scope"]}</td>'
                     f'<td class="addr">{addr}</td>'
                     f'<td style="text-align:center">{sz}</td>'
                     f'<td style="text-align:center">{init}</td></tr>')
    return f"""{err_html}
<div class="summary-grid">
  <div class="summary-card"><div class="summary-num">{total}</div><div class="summary-label">Total Symbols</div></div>
  <div class="summary-card"><div class="summary-num">{funcs}</div><div class="summary-label">Functions</div></div>
  <div class="summary-card"><div class="summary-num">{vars_}</div><div class="summary-label">Variables</div></div>
</div>
<div class="output-block">
  <div class="output-block-header">Symbol Table</div>
  <table class="sym-table">
    <thead><tr><th>Name</th><th>Type</th><th>Kind</th><th>Scope</th><th>Address</th><th>Size</th><th>Init</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

def render_semantic(errors):
    checks = [
        ("All identifiers declared before use","No undeclared variables or functions"),
        ("No redeclarations in same scope","Each name declared once per scope"),
        ("Function call argument counts","Argument count matches parameter count"),
        ("Return type compatibility","Return expression matches function type"),
        ("Assignment type compatibility","int ↔ float implicit widening allowed"),
    ]
    err_html = f'<div class="error-box">{"<br>".join("✕  "+_h(e) for e in errors)}</div>' if errors else ""
    checks_html = ""
    for label, sub in checks:
        is_err = any(label.lower().split()[0] in e.lower() for e in errors)
        cls  = "sem-err" if is_err else "sem-ok"
        icon = "✕" if is_err else "✓"
        checks_html += f'<div class="sem-check {cls}"><div class="sem-icon">{icon}</div><div><div class="sem-title">{label}</div><div class="sem-sub">{sub}</div></div></div>'
    footer = (f'<div style="margin-top:16px;padding:12px 16px;background:var(--bg3);border-radius:8px;font-size:13px;color:var(--red)">⚠ Semantic analysis found {len(errors)} error(s)</div>'
              if errors else
              '<div style="margin-top:16px;padding:12px 16px;background:#0d2018;border:1px solid #1a3a2a;border-radius:8px;font-size:13px;color:var(--green)">✓ Semantic analysis passed — no errors found</div>')
    return err_html + checks_html + footer

def render_tac(lines):
    non_empty = [l for l in lines if l.strip()]
    fn_count  = sum(1 for l in lines if l.strip().startswith("FUNC_BEGIN"))
    tmp_count = sum(1 for l in lines if re.search(r't\d+\s*=', l))
    body = ""
    lnum = 0
    for raw in lines:
        l = raw.strip()
        if not l: body += "<br>"; continue
        lnum += 1
        if l.startswith("FUNC_"): c = "tac-func"
        elif l.endswith(":"): c = "tac-label"
        elif l.startswith("DECLARE") or l.startswith("PARAM_DECL"): c = "tac-declare"
        elif l.startswith("RETURN"): c = "tac-return"
        elif l.startswith("IF_FALSE") or l.startswith("GOTO"): c = "tac-keyword"
        else: c = "tac-assign"
        text = re.sub(r'\b(t\d+)\b', r'<span class="tac-temp">\1</span>', _h(l))
        body += f'<div class="tac-line"><span class="tac-linenum">{lnum}</span><span class="tac-instr {c}">{text}</span></div>'
    return f"""
<div class="summary-grid">
  <div class="summary-card"><div class="summary-num">{len(non_empty)}</div><div class="summary-label">Instructions</div></div>
  <div class="summary-card"><div class="summary-num">{fn_count}</div><div class="summary-label">Functions</div></div>
  <div class="summary-card"><div class="summary-num">{tmp_count}</div><div class="summary-label">Temporaries</div></div>
</div>
<div class="output-block">
  <div class="output-block-header">Three Address Code (TAC / IR) <span class="badge">{len(non_empty)} instructions</span></div>
  <div class="output-pre">{body}</div>
</div>"""

def render_asm(lines):
    instr = sum(1 for l in lines if l.strip() and not l.strip().startswith(";")
                and not re.match(r'^\.?[a-zA-Z_]\w*:$', l.strip()))
    body = ""
    for i, raw in enumerate(lines):
        l = raw.strip()
        if not l: body += "<br>"; continue
        n = i + 1
        if l.startswith(";"):
            body += f'<div class="asm-line"><span class="asm-linenum">{n}</span><span class="asm-comment">{_h(raw)}</span></div>'
            continue
        if re.match(r'^[a-zA-Z_]\w*:$', l):
            body += f'<div class="asm-line"><span class="asm-linenum">{n}</span><span class="asm-label">{_h(raw)}</span></div>'
            continue
        if l.startswith(".") and l.endswith(":"):
            body += f'<div class="asm-line"><span class="asm-linenum">{n}</span><span class="asm-label">{_h(raw)}</span></div>'
            continue
        colored = _h(raw)
        colored = re.sub(r'\b(mov|add|sub|imul|idiv|push|pop|call|ret|jmp|je|jne|jl|jg|jle|jge|cmp|cdq|setl|setg|sete|setne|setle|setge|movzx)\b',
                         r'<span class="asm-op">\1</span>', colored)
        colored = re.sub(r'\b(eax|ebx|ecx|edx|esp|ebp|esi|edi|bp|sp|al|ah)\b',
                         r'<span class="asm-reg">\1</span>', colored)
        colored = re.sub(r'\[([^\]]+)\]', r'<span class="asm-mem">[\1]</span>', colored)
        colored = re.sub(r'\b(\d+)\b', r'<span class="asm-imm">\1</span>', colored)
        body += f'<div class="asm-line"><span class="asm-linenum">{n}</span><span class="asm-instr">{colored}</span></div>'
    return f"""
<div class="output-block">
  <div class="output-block-header">x86 Assembly &nbsp;(Intel syntax, 32-bit) <span class="badge">{instr} instructions</span></div>
  <div class="output-pre">{body}</div>
</div>"""


# ══════════════════════════════════════════════════════════════
#  LL(1) Grammar Analyzer Dialog
# ══════════════════════════════════════════════════════════════

DARK_STYLE = f"""
QDialog, QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
}}
QLabel {{
    color: {TEXT};
    font-size: 14px;
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px;
    color: {MUTED};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
QPlainTextEdit, QTextEdit {{
    background: {BG2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: 'Cascadia Code', 'Fira Code', 'Courier New', monospace;
    font-size: 14px;
    padding: 8px;
    selection-background-color: {BORDER};
}}
QPushButton {{
    background: {BG3};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 13px;
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
}}
QPushButton#runBtn {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT2},stop:1 {ACCENT});
    color: #fff;
    border: none;
    font-weight: 600;
    padding: 9px 26px;
    font-size: 14px;
}}
QPushButton#runBtn:hover {{
    opacity: 0.9;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG2};
    border-radius: 0 6px 6px 6px;
}}
QTabBar::tab {{
    background: {BG3};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 8px 18px;
    font-size: 13px;
    margin-right: 2px;
    border-radius: 5px 5px 0 0;
}}
QTabBar::tab:selected {{
    background: {BG2};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QCheckBox {{
    color: {MUTED};
    font-size: 13px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background: {BG3};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT2};
    border-color: {ACCENT2};
}}
QSpinBox {{
    background: {BG2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 7px;
    font-size: 13px;
}}
QScrollBar:vertical {{
    background: {BG};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
"""

_ARROW_RE = re.compile(r'\s*(?:->|\u2013>|\u2014>|\u2192)\s*')
_PIPE_RE  = re.compile(r'\s*(?:\||\u2223|\uff5c)\s*')

def parse_grammar_text(text: str):
    from collections import OrderedDict

    errors     = []
    nts        = set()
    lines_data = []

    # Pass 1: collect NT names
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = _ARROW_RE.search(line)
        if not m:
            if '->' in line:
                idx = line.index('->')
                left  = line[:idx].strip()
                right = line[idx+2:]
                if left:
                    nts.add(left)
                    lines_data.append((left, right))
                    continue
            errors.append(f'No arrow found: "{line}"')
            continue
        left  = line[:m.start()].strip()
        right = line[m.end():]
        if not left:
            errors.append(f'Empty LHS in: "{line}"')
            continue
        nts.add(left)
        lines_data.append((left, right))

    # Pass 2: tokenize with full NT knowledge
    def tokenize(part: str) -> list:
        tokens = []
        for tok in part.split():
            if tok in ('ε', 'eps', "''", 'epsilon', '\u03b5'):
                tokens.append('ε')
                continue
            if tok in nts or len(tok) == 1:
                tokens.append(tok)
                continue
            if re.match(r'^[a-z0-9_+\-*/%.]+$', tok):
                tokens.append(tok)
                continue
            i = 0
            while i < len(tok):
                matched = False
                for length in range(len(tok) - i, 1, -1):
                    if tok[i:i+length] in nts:
                        tokens.append(tok[i:i+length])
                        i += length
                        matched = True
                        break
                if not matched:
                    tokens.append(tok[i])
                    i += 1
        return tokens

    grammar = OrderedDict()
    for left, right in lines_data:
        prods = []
        for part in _PIPE_RE.split(right):
            part = part.strip()
            if not part:
                continue
            toks = tokenize(part)
            if toks:
                prods.append(toks)
        if prods:
            if left in grammar:
                grammar[left].extend(prods)
            else:
                grammar[left] = prods

    return grammar, errors


class GrammarWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LL(1) Grammar Analyzer")
        self.resize(1000, 740)
        self.setStyleSheet(DARK_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        # ── title bar ─────────────────────────────────────────
        title_row = QHBoxLayout()
        lbl = QLabel("LL(1) Grammar Analyzer")
        lbl.setStyleSheet(f"font-size:19px;font-weight:700;color:{ACCENT};")
        title_row.addWidget(lbl)
        title_row.addStretch()
        hint = QLabel("Write productions like:  S -> a B | ε   (one NT per line)")
        hint.setStyleSheet(f"color:{MUTED};font-size:12px;")
        title_row.addWidget(hint)
        root.addLayout(title_row)

        # ── input area ────────────────────────────────────────
        input_grp = QGroupBox("Grammar Input")
        ig_layout = QVBoxLayout(input_grp)
        ig_layout.setSpacing(10)

        self.grammar_input = QPlainTextEdit()
        self.grammar_input.setPlaceholderText(
            "E -> T E'\n"
            "E' -> + T E' | ε\n"
            "T -> F T'\n"
            "T' -> * F T' | ε\n"
            "F -> ( E ) | id"
        )
        self.grammar_input.setMinimumHeight(150)
        self.grammar_input.setMaximumHeight(220)
        ig_layout.addWidget(self.grammar_input)

        # options row — Parsing Table checkbox removed
        opt_row = QHBoxLayout()
        self.chk_lr  = QCheckBox("Remove Left Recursion")
        self.chk_lf  = QCheckBox("Left Factoring")
        self.chk_ff  = QCheckBox("FIRST / FOLLOW Sets")
        self.chk_lr.setChecked(True)
        self.chk_lf.setChecked(True)
        self.chk_ff.setChecked(True)
        for chk in (self.chk_lr, self.chk_lf, self.chk_ff):
            opt_row.addWidget(chk)
        opt_row.addStretch()

        run_btn = QPushButton("▶  Analyze")
        run_btn.setObjectName("runBtn")
        run_btn.clicked.connect(self._run)
        run_btn.setMinimumWidth(140)
        opt_row.addWidget(run_btn)

        clr_btn = QPushButton("Clear")
        clr_btn.clicked.connect(self._clear)
        opt_row.addWidget(clr_btn)

        ig_layout.addLayout(opt_row)
        root.addWidget(input_grp)

        # ── output tabs — Parsing Table tab removed ───────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.out_original = self._make_output_tab()
        self.out_lr       = self._make_output_tab()
        self.out_lf       = self._make_output_tab()
        self.out_ff       = self._make_output_tab()

        self.tabs.addTab(self.out_original, "Original")
        self.tabs.addTab(self.out_lr,       "↺ Left Recursion")
        self.tabs.addTab(self.out_lf,       "⇥ Left Factoring")
        self.tabs.addTab(self.out_ff,       "∈ FIRST / FOLLOW")

        root.addWidget(self.tabs)

        # ── status bar ────────────────────────────────────────
        self.status_lbl = QLabel("Enter a grammar above and click Analyze.")
        self.status_lbl.setStyleSheet(f"color:{MUTED};font-size:12px;padding:2px 0;")
        root.addWidget(self.status_lbl)

    def _make_output_tab(self) -> QPlainTextEdit:
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setLineWrapMode(QPlainTextEdit.NoWrap)
        w.setStyleSheet(f"""
            QPlainTextEdit {{
                background:{BG2};
                color:{TEXT};
                border:none;
                font-family:'Cascadia Code','Fira Code','Courier New',monospace;
                font-size:15px;
                padding:14px;
            }}
        """)
        return w

    def _clear(self):
        self.grammar_input.clear()
        for w in (self.out_original, self.out_lr, self.out_lf, self.out_ff):
            w.clear()
        self.status_lbl.setText("Cleared.")

    def _set_out(self, widget, text):
        widget.setPlainText(text)

    def _run(self):
        raw = self.grammar_input.toPlainText().strip()
        if not raw:
            self.status_lbl.setText("⚠  Please enter a grammar first.")
            return

        grammar, parse_errors = parse_grammar_text(raw)

        if parse_errors:
            msg = "Parse errors:\n" + "\n".join(parse_errors)
            self._set_out(self.out_original, msg)
            self.status_lbl.setText(f"⚠  {len(parse_errors)} parse error(s).")
            self.tabs.setCurrentIndex(0)
            return

        if not grammar:
            self.status_lbl.setText("⚠  No valid productions found.")
            return

        # Original grammar
        self._set_out(self.out_original, format_grammar(grammar, "── Original Grammar"))

        # Left Recursion
        g_lr = grammar
        if self.chk_lr.isChecked():
            try:
                g_lr = remove_left_recursion(grammar)
                self._set_out(self.out_lr,
                    format_grammar(grammar, "── Before (Original)") + "\n\n" +
                    format_grammar(g_lr,    "── After Removing Left Recursion"))
            except Exception as e:
                self._set_out(self.out_lr, f"Error: {e}")
                g_lr = grammar
        else:
            self._set_out(self.out_lr, "(skipped — uncheck to enable)")

        # Left Factoring
        g_lf = g_lr
        if self.chk_lf.isChecked():
            try:
                g_lf = left_factoring(g_lr)
                self._set_out(self.out_lf,
                    format_grammar(g_lr, "── Before Left Factoring") + "\n\n" +
                    format_grammar(g_lf, "── After Left Factoring"))
            except Exception as e:
                self._set_out(self.out_lf, f"Error: {e}")
                g_lf = g_lr
        else:
            self._set_out(self.out_lf, "(skipped — uncheck to enable)")

        # FIRST / FOLLOW — always on original grammar
        if self.chk_ff.isChecked():
            try:
                first  = compute_first(grammar)
                follow = compute_follow(grammar, first)
                self._set_out(self.out_ff,
                    format_grammar(grammar, "── Grammar Used (Original)") + "\n\n" +
                    format_first_follow(first, follow))
            except Exception as e:
                self._set_out(self.out_ff, f"Error: {e}")
        else:
            self._set_out(self.out_ff, "(skipped — uncheck to enable)")

        nt_count = len(g_lf)
        self.status_lbl.setText(
            f"✓  Analysis complete — {nt_count} non-terminal(s) in final grammar.")
        self.tabs.setCurrentIndex(0)


# ══════════════════════════════════════════════════════════════
#  Full HTML page (editor + compiler UI)
# ══════════════════════════════════════════════════════════════
DEFAULT_SRC = SAMPLES["func"]

def build_full_page(bridge_name="pyBridge"):
    samples_js = json.dumps({k: v for k, v in SAMPLES.items()})
    default_escaped = DEFAULT_SRC.replace("`", "\\`").replace("$","\\$")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mini C Compiler</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/clike/clike.min.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:    #282A36;
  --bg2:   #21222C;
  --bg3:   #2E303E;
  --border:#44475A;
  --cyan:  #8BE9FD;
  --purple:#BD93F9;
  --green: #50FA7B;
  --yellow:#F1FA8C;
  --red:   #FF5555;
  --pink:  #FF79C6;
  --orange:#FFB86C;
  --text:  #F8F8F2;
  --muted: #6272A4;
  --accent:var(--cyan);
  --accent2:var(--purple);
  --mono:'Cascadia Code','Fira Code','JetBrains Mono','Courier New',monospace;
  --sans:'Segoe UI',system-ui,sans-serif;
}}

html,body{{height:100%;overflow:hidden}}
body{{
  background:var(--bg);color:var(--text);
  font-family:var(--sans);
  display:flex;flex-direction:column;
  contain:strict;
}}

header{{
  background:var(--bg2);
  border-bottom:2px solid var(--border);
  padding:0 18px;height:52px;
  display:flex;align-items:center;gap:12px;
  flex-shrink:0;z-index:10;
}}
.logo{{display:flex;align-items:center;gap:9px}}
.logo-icon{{
  width:30px;height:30px;
  background:linear-gradient(135deg,var(--purple),var(--cyan));
  border-radius:6px;
  display:flex;align-items:center;justify-content:center;
  font-size:14px;font-weight:800;color:#21222C;
  flex-shrink:0;
}}
.logo-text{{font-size:13.5px;font-weight:700;letter-spacing:.2px}}
.logo-sub{{font-size:10px;color:var(--muted);letter-spacing:.4px}}
.spacer{{flex:1}}

.ll1-btn{{
  background:var(--bg3);
  border:1px solid var(--border);
  color:var(--purple);
  padding:6px 14px;border-radius:6px;
  font-size:11.5px;font-weight:600;cursor:pointer;
  transition:border-color 80ms,background 80ms;
  display:flex;align-items:center;gap:6px;
}}
.ll1-btn:hover{{border-color:var(--purple);background:#38294a}}
.compile-btn{{
  background:linear-gradient(135deg,var(--purple) 0%,var(--cyan) 100%);
  border:none;color:#21222C;
  padding:7px 18px;border-radius:6px;
  font-size:12.5px;font-weight:700;cursor:pointer;
  display:flex;align-items:center;gap:6px;
  transition:filter 80ms;
}}
.compile-btn:hover{{filter:brightness(1.1)}}
.compile-btn:active{{filter:brightness(.95)}}
.compile-btn:disabled{{filter:opacity(.35);cursor:not-allowed}}
.compile-btn svg{{width:13px;height:13px}}
.spinner{{
  display:inline-block;width:12px;height:12px;
  border:2px solid rgba(33,34,44,.25);border-top-color:#21222C;
  border-radius:50%;animation:spin .5s linear infinite;
}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}

.progress-bar{{height:2px;background:var(--border);flex-shrink:0}}
.progress-fill{{
  height:100%;width:0%;
  background:linear-gradient(90deg,var(--purple),var(--cyan));
  transition:width 200ms linear;
}}

.main{{display:flex;flex:1;overflow:hidden;contain:layout}}

.left-panel{{
  min-width:200px;
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;
  background:var(--bg2);contain:layout;
}}
.panel-header{{
  padding:8px 13px;
  border-bottom:1px solid var(--border);
  font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:1.4px;color:var(--muted);
  display:flex;align-items:center;gap:7px;flex-shrink:0;
}}
.dot{{
  width:6px;height:6px;border-radius:50%;
  background:var(--green);
  animation:blink 2s step-end infinite;
}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.editor-wrap{{flex:1;overflow:hidden;contain:strict}}

.CodeMirror{{
  height:100%!important;
  font-size:13px;font-family:var(--mono)!important;
  background:var(--bg2)!important;color:var(--text)!important;
  border:none;line-height:1.6;
}}
.CodeMirror-scroll{{contain:strict}}
.CodeMirror-gutters{{background:var(--bg2)!important;border-right:1px solid var(--border)!important}}
.CodeMirror-linenumber{{color:var(--muted)!important;font-size:11px}}
.CodeMirror-selected{{background:#44475A!important}}
.CodeMirror-cursor{{border-left:2px solid var(--cyan)!important}}
.cm-keyword{{color:#FF79C6!important;font-weight:600}}
.cm-type{{color:#8BE9FD!important}}
.cm-number{{color:#BD93F9!important}}
.cm-comment{{color:#6272A4!important;font-style:italic}}
.cm-string{{color:#F1FA8C!important}}
.cm-def{{color:#50FA7B!important}}
.cm-operator,.cm-punctuation{{color:#FF79C6!important}}
.cm-variable{{color:#F8F8F2!important}}

.sample-btns{{
  padding:7px 13px;border-top:1px solid var(--border);
  display:flex;gap:5px;flex-wrap:wrap;flex-shrink:0;
}}
.sample-btn{{
  background:var(--bg3);border:1px solid var(--border);
  color:var(--muted);padding:3px 8px;border-radius:4px;
  font-size:11px;cursor:pointer;
  transition:border-color 60ms,color 60ms;
}}
.sample-btn:hover{{border-color:var(--cyan);color:var(--cyan)}}

.drag-handle{{
  width:3px;background:var(--border);
  cursor:col-resize;flex-shrink:0;
  transition:background 60ms;
}}
.drag-handle:hover,.drag-handle.active{{background:var(--purple)}}

.right-panel{{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:260px;contain:layout}}

.phase-tabs{{
  display:flex;background:var(--bg2);
  border-bottom:1px solid var(--border);
  overflow-x:auto;scrollbar-width:none;flex-shrink:0;
}}
.phase-tabs::-webkit-scrollbar{{display:none}}
.phase-tab{{
  padding:8px 14px;font-size:11px;font-weight:700;
  color:var(--muted);cursor:pointer;white-space:nowrap;
  border-bottom:2px solid transparent;
  transition:color 60ms,border-color 60ms;
  display:flex;align-items:center;gap:5px;
  user-select:none;letter-spacing:.3px;
}}
.phase-tab:hover{{color:var(--text)}}
.phase-tab.active{{color:var(--cyan);border-bottom-color:var(--cyan)}}
.phase-tab.done .phase-num{{background:var(--green);color:#21222C}}
.phase-tab.error .phase-num{{background:var(--red);color:#fff}}
.phase-num{{
  width:16px;height:16px;border-radius:50%;
  background:var(--bg3);color:var(--muted);
  font-size:9px;font-weight:800;
  display:flex;align-items:center;justify-content:center;
  transition:background 100ms,color 100ms;
}}
.phase-content{{flex:1;overflow:auto;padding:16px 20px;contain:layout}}

.output-block{{
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:7px;overflow:hidden;
  margin-bottom:12px;
}}
.output-block-header{{
  padding:6px 12px;
  background:var(--bg3);
  border-bottom:1px solid var(--border);
  font-size:10px;font-weight:700;color:var(--muted);
  text-transform:uppercase;letter-spacing:1.2px;
  display:flex;align-items:center;justify-content:space-between;
}}
.badge{{
  padding:1px 7px;border-radius:3px;font-size:9.5px;font-weight:700;
  background:rgba(139,233,253,.1);
  color:var(--cyan);border:1px solid rgba(139,233,253,.2);
}}
.output-pre{{
  padding:12px 14px;
  font-family:var(--mono);font-size:12.5px;
  line-height:1.6;overflow-x:auto;
  white-space:pre;color:var(--text);
}}

.token-table{{width:100%;border-collapse:collapse;font-size:12px;font-family:var(--mono)}}
.token-table th{{
  text-align:left;padding:6px 11px;
  background:var(--bg3);color:var(--muted);
  font-size:9.5px;text-transform:uppercase;letter-spacing:1.2px;
  border-bottom:1px solid var(--border);
}}
.token-table td{{padding:5px 11px;border-bottom:1px solid rgba(68,71,90,.35)}}
.token-table tr:last-child td{{border-bottom:none}}
.token-table tr:hover td{{background:rgba(68,71,90,.35)}}
.tok-type{{color:var(--purple);font-weight:700}}
.tok-kw{{color:var(--pink)}}.tok-id{{color:var(--cyan)}}
.tok-op{{color:var(--pink)}}.tok-lit{{color:var(--yellow)}}.tok-punc{{color:var(--text)}}

.ast-tree{{font-family:var(--mono);font-size:12.5px;line-height:1.8}}
.ast-node:hover{{color:var(--cyan)}}
.ast-type{{color:var(--purple);font-weight:700}}
.ast-attr-name{{color:var(--muted)}}.ast-attr-val{{color:var(--yellow)}}
.ast-connector{{color:rgba(68,71,90,.7)}}

.sym-table{{width:100%;border-collapse:collapse;font-size:12px}}
.sym-table th{{
  text-align:left;padding:6px 11px;
  background:var(--bg3);color:var(--muted);
  font-size:9.5px;text-transform:uppercase;letter-spacing:1.2px;
  border-bottom:1px solid var(--border);white-space:nowrap;
}}
.sym-table td{{
  padding:5px 11px;
  border-bottom:1px solid rgba(68,71,90,.35);
  font-family:var(--mono);
}}
.sym-table tr:hover td{{background:rgba(68,71,90,.35)}}
.scope-label{{
  padding:4px 11px;background:var(--bg);
  color:var(--purple);font-size:9.5px;font-weight:700;
  text-transform:uppercase;letter-spacing:1.2px;
  border-bottom:1px solid var(--border);
}}
.kind-func{{color:var(--purple)}}.kind-var{{color:var(--cyan)}}.kind-param{{color:var(--orange)}}
.init-yes{{color:var(--green)}}.init-no{{color:var(--red)}}.addr{{color:var(--muted)}}

.summary-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-bottom:16px}}
.summary-card{{
  background:var(--bg3);border:1px solid var(--border);
  border-radius:7px;padding:12px;text-align:center;
  transition:border-color 60ms;
}}
.summary-card:hover{{border-color:var(--purple)}}
.summary-num{{
  font-size:24px;font-weight:800;color:var(--cyan);
  font-family:var(--mono);letter-spacing:-1px;
}}
.summary-label{{
  font-size:9.5px;color:var(--muted);margin-top:3px;
  text-transform:uppercase;letter-spacing:1.2px;font-weight:700;
}}

.error-box{{
  background:rgba(255,85,85,.07);
  border:1px solid rgba(255,85,85,.3);
  border-left:3px solid var(--red);
  border-radius:6px;padding:12px;margin-bottom:12px;
  font-family:var(--mono);font-size:12px;
  color:var(--red);line-height:1.6;
}}
.sem-check{{
  display:flex;align-items:flex-start;gap:9px;
  padding:8px 12px;border-radius:6px;margin-bottom:6px;
  background:var(--bg3);border:1px solid var(--border);
}}
.sem-icon{{font-size:14px;flex-shrink:0;margin-top:1px}}
.sem-ok{{border-left:3px solid var(--green)}}.sem-ok .sem-icon{{color:var(--green)}}
.sem-err{{border-left:3px solid var(--red)}}.sem-err .sem-icon{{color:var(--red)}}
.sem-title{{font-size:12px;font-weight:600}}
.sem-sub{{font-size:10.5px;color:var(--muted);margin-top:2px}}

.tac-line{{display:flex;gap:9px;padding:1px 0}}
.tac-linenum{{color:var(--muted);font-size:11px;min-width:26px;text-align:right}}
.tac-instr{{font-family:var(--mono);font-size:12px}}
.tac-func{{color:var(--cyan);font-weight:700}}
.tac-label{{color:var(--yellow);font-weight:600}}
.tac-declare{{color:var(--muted)}}
.tac-assign{{color:var(--text)}}
.tac-temp{{color:var(--purple)}}
.tac-return{{color:var(--green)}}
.tac-keyword{{color:var(--pink)}}

.asm-line{{display:flex;gap:9px;padding:1px 0}}
.asm-linenum{{color:var(--muted);font-size:11px;min-width:26px;text-align:right}}
.asm-instr{{font-family:var(--mono);font-size:12px}}
.asm-comment{{color:var(--muted);font-style:italic}}
.asm-label{{color:var(--yellow);font-weight:700}}
.asm-op{{color:var(--pink);font-weight:600}}
.asm-reg{{color:var(--orange)}}
.asm-mem{{color:var(--yellow)}}
.asm-imm{{color:var(--purple)}}

.status-bar{{
  background:var(--bg2);
  border-top:1px solid var(--border);
  padding:4px 16px;
  display:flex;align-items:center;gap:12px;
  font-size:10.5px;color:var(--muted);flex-shrink:0;
}}
.status-dot{{
  width:6px;height:6px;border-radius:50%;
  background:var(--muted);
  transition:background 150ms;
}}
.status-dot.ok{{background:var(--green)}}
.status-dot.err{{background:var(--red)}}
.status-dot.run{{background:var(--yellow);animation:blink .8s step-end infinite}}

.welcome{{
  display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  height:100%;gap:10px;color:var(--muted);text-align:center;
}}
.welcome-icon{{font-size:42px;opacity:.18}}
.welcome h3{{font-size:14px;font-weight:700;color:var(--text);opacity:.55;letter-spacing:.3px}}
.welcome p{{font-size:12px;max-width:280px;line-height:1.65}}
.welcome strong{{color:var(--cyan)}}

::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--border);border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:var(--muted)}}
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">C</div>
    <div>
      <div class="logo-text">Mini C Compiler</div>
      <div class="logo-sub">6-Phase Educational Compiler</div>
    </div>
  </div>
  <div class="spacer"></div>
  <button class="ll1-btn" onclick="openLL1()">⊞ LL(1) Grammar</button>
  <button class="compile-btn" id="compileBtn" onclick="runCompiler()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5,3 19,12 5,21"/></svg>
    Compile
  </button>
</header>

<div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>

<div class="main" id="mainArea">
  <div class="left-panel" id="leftPanel">
    <div class="panel-header">
      <div class="dot"></div>
      Source Code — C
    </div>
    <div class="editor-wrap">
      <textarea id="codeInput"></textarea>
    </div>
    <div class="sample-btns">
      <span style="font-size:11px;color:var(--muted);align-self:center">Load:</span>
      <button class="sample-btn" onclick="loadSample('simple')">Simple</button>
      <button class="sample-btn" onclick="loadSample('arith')">Arithmetic</button>
      <button class="sample-btn" onclick="loadSample('if')">If/Else</button>
      <button class="sample-btn" onclick="loadSample('while')">While</button>
      <button class="sample-btn" onclick="loadSample('func')">Functions</button>
    </div>
  </div>

  <div class="drag-handle" id="dragHandle"></div>

  <div class="right-panel">
    <div class="phase-tabs">
      <div class="phase-tab" onclick="showPhase(1)" id="tab1"><span class="phase-num" id="pnum1">1</span> Tokens</div>
      <div class="phase-tab" onclick="showPhase(2)" id="tab2"><span class="phase-num" id="pnum2">2</span> AST</div>
      <div class="phase-tab" onclick="showPhase(3)" id="tab3"><span class="phase-num" id="pnum3">3</span> Symbol Table</div>
      <div class="phase-tab" onclick="showPhase(4)" id="tab4"><span class="phase-num" id="pnum4">4</span> Semantic</div>
      <div class="phase-tab" onclick="showPhase(5)" id="tab5"><span class="phase-num" id="pnum5">5</span> TAC / IR</div>
      <div class="phase-tab" onclick="showPhase(6)" id="tab6"><span class="phase-num" id="pnum6">6</span> Assembly</div>
    </div>
    <div class="phase-content" id="phaseContent">
      <div class="welcome">
        <div class="welcome-icon">⚙</div>
        <h3>Ready to Compile</h3>
        <p>Write or load a C program on the left, then click <strong>Compile</strong> to run all 6 phases.<br><br>Use <strong>LL(1) Grammar</strong> button for CFG analysis.</p>
      </div>
    </div>
  </div>
</div>

<div class="status-bar">
  <div class="status-dot" id="statusDot"></div>
  <span id="statusText">No source compiled yet</span>
  <div style="flex:1"></div>
  <span id="statusStats"></span>
</div>

<script>
const SAMPLES = {samples_js};
let editor, compiled=false, currentPhase=1;
let phaseHtml = {{}};
let bridge = null;

new QWebChannel(qt.webChannelTransport, function(channel) {{
  bridge = channel.objects.pyBridge;
}});

window.onload = () => {{
  editor = CodeMirror.fromTextArea(document.getElementById('codeInput'), {{
    mode: 'text/x-csrc', lineNumbers: true, theme: 'default',
    indentUnit: 4, tabSize: 4, indentWithTabs: false, autofocus: true,
    extraKeys: {{ 'Ctrl-Enter': runCompiler, 'Cmd-Enter': runCompiler }}
  }});
  editor.setValue(`{default_escaped}`);
  initDragHandle();
}};

function initDragHandle() {{
  const handle = document.getElementById('dragHandle');
  const left   = document.getElementById('leftPanel');
  let dragging = false, startX = 0, startW = 0;

  handle.addEventListener('mousedown', e => {{
    dragging = true;
    startX   = e.clientX;
    startW   = left.getBoundingClientRect().width;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }});

  document.addEventListener('mousemove', e => {{
    if (!dragging) return;
    const delta = e.clientX - startX;
    const newW  = Math.max(180, Math.min(startW + delta, window.innerWidth - 340));
    left.style.width = newW + 'px';
    left.style.minWidth = newW + 'px';
    left.style.maxWidth = newW + 'px';
    editor && editor.refresh();
  }});

  document.addEventListener('mouseup', () => {{
    if (dragging) {{
      dragging = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      editor && editor.refresh();
    }}
  }});
}}

function loadSample(name) {{
  editor.setValue(SAMPLES[name]);
  editor.focus();
}}

function showPhase(n) {{
  document.querySelectorAll('.phase-tab').forEach((t,i)=>t.classList.toggle('active',i+1===n));
  currentPhase = n;
  document.getElementById('phaseContent').innerHTML =
    phaseHtml[n] || '<div class="welcome"><div class="welcome-icon">⚙</div><h3>Ready to Compile</h3></div>';
}}

function setProgress(pct) {{ document.getElementById('progressFill').style.width=pct+'%'; }}

function setStatus(state,msg) {{
  const dot=document.getElementById('statusDot');
  dot.className='status-dot'+(state?' '+state:'');
  document.getElementById('statusText').textContent=msg;
}}

function openLL1() {{
  if (bridge) bridge.openLL1();
}}

function runCompiler() {{
  const src = editor.getValue().trim();
  if (!src) return;
  const btn = document.getElementById('compileBtn');
  btn.disabled=true;
  btn.innerHTML='<div class="spinner"></div> Compiling...';
  setStatus('run','Compiling...');
  setProgress(0);
  if (bridge) bridge.compile(src);
}}

function receiveResults(data) {{
  phaseHtml = data.phases;
  const errors = data.errors;
  const tokenCount = data.tokenCount;
  const tacCount = data.tacCount;

  for (let i=1;i<=6;i++) {{
    const tab=document.getElementById('tab'+i);
    const num=document.getElementById('pnum'+i);
    const hasErr = errors.length>0 && i>=3;
    tab.classList.remove('done','error');
    if (!hasErr) {{ tab.classList.add('done'); num.textContent='✓'; }}
    else if (i===4) {{ tab.classList.add('error'); num.textContent='✕'; }}
    else {{ num.textContent=i; }}
  }}

  const btn=document.getElementById('compileBtn');
  btn.disabled=false;
  btn.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5,3 19,12 5,21"/></svg> Compile';
  setProgress(100);
  setTimeout(()=>setProgress(0),1200);

  compiled=true;
  if (errors.length>0) setStatus('err','Compilation failed — '+errors.length+' error(s)');
  else setStatus('ok','Compiled successfully — '+tokenCount+' tokens, '+tacCount+' TAC instructions');

  showPhase(1);
}}
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  Bridge — Python ↔ JavaScript
# ══════════════════════════════════════════════════════════════
class Bridge(QObject):
    def __init__(self, window):
        super().__init__()
        self._win = window

    @pyqtSlot(str)
    def compile(self, src):
        self._win.run_compiler(src)

    @pyqtSlot(str)
    def loadSample(self, name):
        src = SAMPLES.get(name, "")
        escaped = src.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        self._win.page.runJavaScript(f"editor.setValue(`{escaped}`);")

    @pyqtSlot()
    def openLL1(self):
        self._win.open_ll1_window()


# ══════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini C Compiler  —  6-Phase Educational Compiler")
        self.resize(1400, 860)
        self._ll1_window = None
        self._setup_ui()

    def _setup_ui(self):
        self.view = QWebEngineView()
        self.view.page().setBackgroundColor(QColor(BG))
        self.setCentralWidget(self.view)

        self.channel = QWebChannel()
        self.bridge  = Bridge(self)
        self.channel.registerObject("pyBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.page = self.view.page()

        html = build_full_page()
        self.view.setHtml(html, QUrl("qrc:/"))

    def open_ll1_window(self):
        if self._ll1_window is None or not self._ll1_window.isVisible():
            self._ll1_window = GrammarWindow(self)
        self._ll1_window.show()
        self._ll1_window.raise_()
        self._ll1_window.activateWindow()

    def run_compiler(self, src: str):
        try:
            result = compile_all(src)
        except Exception as e:
            result = dict(tokens=[], ast=None, parse_error=str(e),
                          symbols={"scopes":[],"errors":[str(e)]},
                          errors=[str(e)], tac=[], asm=[])

        phases = {
            "1": render_tokens(result["tokens"]),
            "2": render_ast(result["ast"], result.get("parse_error")),
            "3": render_sym(result["symbols"]),
            "4": render_semantic(result["errors"]),
            "5": render_tac(result["tac"]),
            "6": render_asm(result["asm"]),
        }

        phase_entries = ",".join(
            f'{k}:`{_j(v)}`' for k, v in phases.items()
        )
        js = f"""receiveResults({{
  phases: {{{phase_entries}}},
  errors: {json.dumps(result["errors"])},
  tokenCount: {len(result["tokens"])},
  tacCount: {len([l for l in result["tac"] if l.strip()])}
}});"""
        self.page.runJavaScript(js)


# ══════════════════════════════════════════════════════════════
def launch_gui():
    app = QApplication(sys.argv)
    app.setApplicationName("Mini C Compiler")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    launch_gui()