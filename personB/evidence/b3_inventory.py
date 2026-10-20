"""
B3 evidence: inventory of the Python modules under plugins/ and .github/scripts/.

Run from the ROOT of the claude-code clone:
    python ../recon/b3_inventory.py | tee ../recon/15-b3-python.txt

For each module it prints: lines, classes, functions, the longest function, the module-level
names that are assigned a list/dict/set (candidate "information holders"), and which other
local modules it imports (fan-out). Python 3.10+, standard library only.
"""
import ast
import pathlib
import subprocess

files = subprocess.check_output(
    ['git', 'ls-files', 'plugins/*.py', '.github/scripts/*.py'], text=True).split()
local = {pathlib.Path(f).stem for f in files} | {'hookify'}

print(f"{'file':72s} {'lines':>5s} {'cls':>3s} {'fn':>3s} {'maxfn':>5s}  data-tables | fan-out")
for f in sorted(files):
    src = pathlib.Path(f).read_text(encoding='utf-8')
    if not src.strip():
        print(f"{f:72s} {0:5d}   (empty file)")
        continue
    tree = ast.parse(src)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    longest = max((n.end_lineno - n.lineno + 1 for n in fns), default=0)
    tables = []
    for n in tree.body:
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(n, 'value', None),
                                                                      (ast.List, ast.Dict, ast.Set)):
            tg = n.targets[0] if isinstance(n, ast.Assign) else n.target
            if isinstance(tg, ast.Name):
                tables.append(tg.id)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split('.')[0])
    fan = sorted(m for m in mods if m in local and m != pathlib.Path(f).stem)
    print(f"{f:72s} {len(src.splitlines()):5d} {len(classes):3d} {len(fns):3d} {longest:5d}  "
          f"{','.join(tables[:4]) or '-'} | {','.join(fan) or '-'}")
