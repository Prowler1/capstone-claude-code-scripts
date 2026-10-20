"""
M5c helper: third-party Python modules that are imported but declared nowhere.

Run from the ROOT of the claude-code clone (it calls `git ls-files`):
    python personB/measure/m5_imports.py
Python 3.10+ (uses sys.stdlib_module_names), standard library only.
A module is "local" if its name matches the stem of any tracked .py file or a folder in its path.
"""
import ast
import pathlib
import subprocess
import sys

files = subprocess.check_output(['git', 'ls-files', '*.py'], text=True).split()
local = {p for f in files for p in pathlib.Path(f).with_suffix('').parts}
third = {}
for f in files:
    try:
        tree = ast.parse(pathlib.Path(f).read_text(encoding='utf-8'))
    except Exception as e:
        print('skipped', f, e)
        continue
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            mods = [n.module]
        else:
            continue
        for m in mods:
            top = m.split('.')[0]
            if top not in sys.stdlib_module_names and top not in local:
                third.setdefault(top, set()).add(f)

print(f'{len(files)} Python files scanned; {len(third)} third-party module(s) imported')
for k, v in sorted(third.items()):
    print(f'  {k}: {sorted(v)}')
