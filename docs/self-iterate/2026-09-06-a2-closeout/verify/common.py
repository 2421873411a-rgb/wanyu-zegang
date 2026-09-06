"""shared helpers for r* verify scripts — batch 3 (A2 收口, copied from batch 2)"""
import os, re, sys, glob, json, subprocess

ROOT = r'E:\zcode\择岗'
SITE = os.path.join(ROOT, '网站')
SRC = os.path.join(ROOT, '项目源码')
RUN = os.path.join(ROOT, r'docs\self-iterate\2026-09-06-a2-closeout')

_results = []

def check(name, ok, detail=''):
    _results.append((name, bool(ok), detail))
    print(('PASS' if ok else 'FAIL'), '|', name, ('| ' + detail if detail else ''))
    return bool(ok)

def finish():
    fails = [r for r in _results if not r[1]]
    print(f"== {len(_results)-len(fails)}/{len(_results)} checks passed ==")
    sys.exit(1 if fails else 0)

def read(p, binary=False):
    with open(p, 'rb' if binary else 'r', encoding=None if binary else 'utf-8', errors='replace') as f:
        return f.read()

def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True).stdout
