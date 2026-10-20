"""
B3 skim: for three modules, print the module docstring and, for every top-level function, its start line, its length
and the first line of its docstring, plus the module-level names. Use it to confirm the role stereotypes in the report.

Run from the ROOT of the claude-code clone:
    python ../recon/b3_skim.py | tee ../recon/18-b3-skim.txt
Python 3.10+, standard library only.
"""
import ast
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'plugins/security-guidance/hooks/'

for name in ['llm.py', 'gitutil.py', '_base.py']:
    src = pathlib.Path(BASE + name).read_text(encoding='utf-8')
    tree = ast.parse(src)
    doc = (ast.get_docstring(tree) or '(no module docstring)').strip().splitlines()
    print(f'===== {name} ({len(src.splitlines())} lines)')
    for line in doc[:6]:
        print('   |', line[:140])
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            d = (ast.get_docstring(n) or '').strip().splitlines()
            print(f'  {n.lineno:5d} {n.end_lineno - n.lineno + 1:4d} lines  {n.name}  {d[0][:90] if d else ""}')
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            tg = n.targets[0] if isinstance(n, ast.Assign) else n.target
            if isinstance(tg, ast.Name) and not tg.id.startswith('__'):
                print(f'  {n.lineno:5d}       module-level  {tg.id}')
