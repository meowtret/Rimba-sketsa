# -*- coding: utf-8 -*-
"""Bangun file terjemahan Rimba Sketsa.

1. Ambil semua string self.tr() per konteks (nama di translate('<ctx>', ...)).
2. Cocokkan dengan kamus i18n/translations_id.py.
3. Tulis i18n/rimba_sketsa_id.ts lalu kompilasi ke .qm dengan lrelease.

Pemakaian (dari folder plugin):
    python tools/build_i18n.py [path/lrelease]
"""
import ast
import glob
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(ROOT, "i18n")


def extract():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
        tree = ast.parse(open(f, encoding="utf-8").read())
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        ctx_of = {}
        for cls in classes:
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "tr":
                    for c in ast.walk(fn):
                        if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "translate":
                            ctx_of[cls.name] = c.args[0].value
        for cls in classes:
            ctx = ctx_of.get(cls.name)
            for c in ast.walk(cls):
                if (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                        and c.func.attr == "tr" and c.args
                        and isinstance(c.args[0], ast.Constant)
                        and isinstance(c.args[0].value, str) and ctx):
                    loc = (os.path.basename(f), c.lineno)
                    out.setdefault(ctx, {}).setdefault(c.args[0].value, []).append(loc)
    return out


def load_dict(lang):
    path = os.path.join(I18N, f"translations_{lang}.py")
    spec = importlib.util.spec_from_file_location("tr_" + lang, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, lang.upper())


PH = re.compile(r"\{[^{}]*\}|%\d")


def main():
    lang = "id"
    strings = extract()
    table = load_dict(lang)
    missing, bad_ph = [], []
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>",
             f'<TS version="2.1" language="{lang}">']
    for ctx in sorted(strings):
        lines.append("<context>")
        lines.append(f"    <name>{escape(ctx)}</name>")
        for src, locs in strings[ctx].items():
            tr = table.get(src)
            if tr is None:
                missing.append((ctx, src))
            elif sorted(PH.findall(src)) != sorted(PH.findall(tr)):
                bad_ph.append((ctx, src, tr))
            lines.append("    <message>")
            for fn, ln in locs:
                lines.append(f'        <location filename="../{fn}" line="{ln}"/>')
            lines.append(f"        <source>{escape(src)}</source>")
            if tr is None:
                lines.append('        <translation type="unfinished"></translation>')
            else:
                lines.append(f"        <translation>{escape(tr)}</translation>")
            lines.append("    </message>")
        lines.append("</context>")
    lines.append("</TS>")
    ts = os.path.join(I18N, f"rimba_sketsa_{lang}.ts")
    open(ts, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    n = sum(len(v) for v in strings.values())
    print(f"{n} string, {len(missing)} belum diterjemahkan, {len(bad_ph)} placeholder tidak cocok")
    for m in missing:
        print("  BELUM:", m)
    for b in bad_ph:
        print("  PLACEHOLDER:", b)
    if missing or bad_ph:
        sys.exit(1)

    lrelease = (sys.argv[1] if len(sys.argv) > 1 else None) or shutil.which("lrelease") \
        or shutil.which("pyside6-lrelease") or shutil.which("lrelease-qt5")
    if not lrelease:
        sys.exit("lrelease tidak ditemukan")
    qm = ts[:-3] + ".qm"
    subprocess.run([lrelease, ts, "-qm", qm], check=True)
    print("OK ->", os.path.relpath(qm, ROOT))


if __name__ == "__main__":
    main()
