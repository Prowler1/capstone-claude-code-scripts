#!/usr/bin/env bash
# M5: supply-chain pinning and declaration.
# Run from the ROOT of the claude-code clone:   bash personB/measure/m5_supply_chain.sh
# Needs: git, GNU grep, Python 3.10+. It prints raw numbers. The install-command hits (M5d)
# and the optional-import sites (M5f) are reviewed by hand, as described in the report.
here="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python || command -v python3)"

echo "commit:  $(git rev-parse HEAD)"
echo "run at:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "tools:   $(git --version); $(grep --version | head -1); $("$PY" --version 2>&1)"
echo

# M5a: external actions (local ./ actions excluded); first party = actions/* and anthropics/*.
# Note: this also matches 'uses:' inside comments, so skim the list printed at the end.
ext=$(grep -rhoE 'uses: [^ ]+' .github/workflows | grep -v 'uses: \./')
third=$(printf '%s\n' "$ext" | grep -vE 'uses: (actions|anthropics)/')
echo "M5a  external Actions pinned to a commit SHA:   $(printf '%s\n' "$ext" | grep -cE '@[0-9a-f]{40}$')/$(printf '%s\n' "$ext" | grep -c .)"
echo "M5a' third-party Actions pinned to a SHA:       $(printf '%s\n' "$third" | grep -cE '@[0-9a-f]{40}$')/$(printf '%s\n' "$third" | grep -c .)"

# M5b: dependency manifests and lockfiles
echo "M5b  dependency manifests / lockfiles:           $(git ls-files | grep -cE '(^|/)(package\.json|package-lock\.json|bun\.lockb?|yarn\.lock|pnpm-lock\.yaml|requirements[^/]*\.txt|pyproject\.toml|Pipfile(\.lock)?|poetry\.lock|go\.(mod|sum)|Cargo\.(toml|lock)|Gemfile(\.lock)?|deno\.(json|lock))$')"

# M5c: undeclared third-party Python packages (AST scan)
echo "M5c  undeclared third-party Python imports:"
"$PY" "$here/m5_imports.py" | sed 's/^/       /'

# M5d: candidate install commands; review every hit by hand
echo "M5d  candidate install commands (review each hit):"
grep -rnE 'npm (install|i|ci)|bun (install|add)|pip install|"pip", *"install"|^ARG .*VERSION' .github scripts .devcontainer plugins 2>/dev/null | sed 's/^/       /'

# M5e: base images pinned by digest
echo "M5e  base images pinned by digest:               $(grep -cE '^FROM .*@sha256:' .devcontainer/Dockerfile)/$(grep -c '^FROM' .devcontainer/Dockerfile)"

# M5f: optional imports; review that each sits inside try/except
echo "M5f  optional-import sites (review each):"
grep -rnE '^\s*(import yaml|from claude_agent_sdk import)' plugins .github 2>/dev/null | sed 's/^/       /'

# M5g: third-party npm imports in mods/ and scripts/ ('claude-code' and 'claude-code/testing' are the engine contract, not packages)
echo "M5g  non-relative TypeScript imports (count, module):"
git ls-files 'mods/*.ts' 'mods/*.tsx' 'scripts/*.ts' | xargs grep -hoE "from ['\"][^./'\"][^'\"]*['\"]" | sort | uniq -c | sort -rn | sed 's/^/       /'

echo
echo "external action references, for review:"
printf '%s\n' "$ext" | sort | uniq -c | sort -rn | sed 's/^/       /'
