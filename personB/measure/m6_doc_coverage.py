"""
M6: documentation coverage of the public surface (v2).

Run from the ROOT of the claude-code clone (it calls `git ls-files`):
    python ../recon/m6_doc_coverage.py

Needs Python 3.10+, no extra packages.
Writes m6_plugins.csv and m6_mods.csv next to this script.

Changes vs v1:
  - Component names are matched with '-', '_' and ' ' treated as the same
    separator (v1 missed "Command Development" for command-development).
  - A strict README rule is computed in the same run.
  - The CSV records whether the plugin has a README at all.
  - Original CSV columns keep their positions; new columns are appended.
"""
import csv
import pathlib
import re
import subprocess
import sys

files = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
fileset = set(files)
out = pathlib.Path(__file__).resolve().parent


def read(p):
    return pathlib.Path(p).read_text(encoding='utf-8', errors='replace')


def flex(name):
    """Regex for a name where '-', '_' and ' ' are interchangeable."""
    parts = re.split(r'[-_ ]+', name.lower())
    return '[-_ ]'.join(re.escape(p) for p in parts if p)


# ---------------------------------------------------------------- plugins
comp = []  # (plugin, kind, name, path)
for f in files:
    m = re.match(r'^plugins/([^/]+)/(commands|agents)/(.+)\.md$', f)
    if m:
        comp.append((m[1], m[2], pathlib.Path(m[3]).name, f))
        continue
    m = re.match(r'^plugins/([^/]+)/skills/([^/]+)/SKILL\.md$', f)
    if m:
        comp.append((m[1], 'skills', m[2], f))


def has_description(text):
    """True if the YAML front matter has a non-empty description."""
    if not text.startswith('---'):
        return False
    end = text.find('\n---', 3)
    lines = text[3:end if end != -1 else None].splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r'description:[ \t]*(.*)$', ln)
        if m:
            v = m[1].strip()
            if v not in ('', '>', '|', '>-', '|-'):
                return True
            # block scalar: the next line must be indented and non-empty
            return (i + 1 < len(lines) and lines[i + 1].strip() != ''
                    and lines[i + 1][0] in ' \t')
    return False


def lenient_rule(name, readme):
    # whole-word mention anywhere in the README
    return re.search(rf'(?<![\w-]){flex(name)}(?![\w-])', readme) is not None


def strict_rule(kind, name, readme):
    # commands must appear as /name; agents and skills in backticks or bold
    if kind == 'commands':
        return re.search(rf'/{flex(name)}(?![\w-])', readme) is not None
    return re.search(rf'[`*]{flex(name)}[`*]', readme) is not None


readmes = {}
rows = []
n_lenient = n_strict = n_desc = 0
missing_readme = set()

for plugin, kind, name, path in comp:
    if plugin not in readmes:
        rp = f'plugins/{plugin}/README.md'
        if rp in fileset:
            readmes[plugin] = read(rp).lower()
        else:
            readmes[plugin] = ''
            missing_readme.add(plugin)
    r = readmes[plugin]
    a = lenient_rule(name, r)
    b = strict_rule(kind, name, r)
    d = has_description(read(path))
    n_lenient += a
    n_strict += b
    n_desc += d
    rows.append([plugin, kind, name, path, int(a), int(d), int(b),
                 int(plugin not in missing_readme)])

with open(out / 'm6_plugins.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['plugin', 'kind', 'name', 'path',
                'in_plugin_readme', 'frontmatter_description',
                'strict_in_readme', 'plugin_has_readme'])
    w.writerows(rows)

n = len(comp)
print(f'Python {sys.version.split()[0]}')
print(f'PLUGINS: {n} components (commands + agents + skills)')
print(f'  lenient README rule (name mentioned): {n_lenient}/{n}')
print(f'  strict README rule (/cmd or `name`/**name**): {n_strict}/{n}')
print(f'  front-matter description: {n_desc}/{n}')
if missing_readme:
    print(f'  plugins with components but NO README: {sorted(missing_readme)}')

# per-plugin breakdown (lenient)
tot, ok = {}, {}
for r in rows:
    tot[r[0]] = tot.get(r[0], 0) + 1
    ok[r[0]] = ok.get(r[0], 0) + r[4]
print('  per plugin (lenient):')
for p in sorted(tot):
    print(f'    {p}: {ok[p]}/{tot[p]}')
print('  undocumented under lenient rule:')
for r in rows:
    if r[4] == 0:
        print(f'    {r[0]} / {r[1]} / {r[2]}')

# ------------------------------------------------------------------- mods
EXPORT = re.compile(
    r'^export\s+(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?'
    r'(?:function\*?|class|interface|type|enum|const|let|var)\s+([A-Za-z_$][\w$]*)')


def has_jsdoc(lines, i):
    j = i - 1
    while j >= 0 and lines[j].strip() == '':
        j -= 1
    if j < 0 or not lines[j].strip().endswith('*/'):
        return False
    while j >= 0 and '/*' not in lines[j]:
        j -= 1
    return j >= 0 and lines[j].strip().startswith('/**')


def is_src(f):
    return (re.match(r'^mods/[^/]+/hooks/.+\.tsx?$', f)
            and not f.endswith('.d.ts')
            and '/tests/' not in f
            and not f.endswith('/index.ts'))


def is_surface(f):
    return bool(re.match(r'^mods/[^/]+/hooks/register\.ts$', f)
                or re.match(r'^mods/[^/]+/types/.+\.d\.ts$', f))


def scan(selector):
    total = doc = 0
    detail = []
    for f in filter(selector, files):
        lines = read(f).splitlines()
        for i, ln in enumerate(lines):
            m = EXPORT.match(ln)
            if m:
                d = has_jsdoc(lines, i)
                total += 1
                doc += d
                detail.append([f, m[1], int(d)])
    return total, doc, detail


t1, d1, det1 = scan(is_src)
t2, d2, det2 = scan(is_surface)
with open(out / 'm6_mods.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['file', 'symbol', 'has_jsdoc'])
    w.writerows(det1 + [r for r in det2 if r not in det1])

print(f'MODS all exports (hooks/, excl. tests, .d.ts, index.ts): {d1}/{t1} with JSDoc')
print(f'MODS entry+types surface (register.ts + mods/*/types/*.d.ts): {d2}/{t2} with JSDoc')
