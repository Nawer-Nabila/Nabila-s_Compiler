#!/usr/bin/env python3
"""
Mini C Compiler — Entry point
Run:  python main.py
"""
import sys, subprocess, os

def check_and_install(pkg, import_name=None):
    imp = import_name or pkg
    try:
        __import__(imp)
        return True
    except ImportError:
        print(f"  Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q",
                                "--break-system-packages"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

if __name__ == "__main__":
    print("Mini C Compiler — starting GUI...")
    check_and_install("PyQt5",     "PyQt5")
    try:
        check_and_install("PyQtWebEngine", "PyQt5.QtWebEngineWidgets")
    except Exception:
        pass  # optional — falls back to QTextEdit renderer

    from gui import launch_gui
    launch_gui()
