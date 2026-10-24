#!/usr/bin/env bash
# Reproduces Person A's metrics M1–M4 at the pinned commit.
# Run from the repository root:  bash personA/measure/run.sh
#
# Pinned commit:  bf2323b3021c9d3db7a31e1e7d61068c3f704497  (2026-10-13)
# Tool versions used for the reported numbers:
#   lizard 1.24.1 (Python 3.14.4)       – M1, Python only
#   ccn.mjs + typescript 5.9.x (Node 25) – M1, TypeScript (see note below)
#   madge 8.0.0                          – M2
#   jscpd 5.4.1                          – M3
#   Claude Code 2.1.300, `claude plugin test` – M4
#
# Note on M1 for TypeScript: lizard 1.24.1 mis-detects the end of a TS
# function whose signature spans several lines and ends in a generic return
# type (`): Promise<boolean> {`). In mods/diff/hooks/register.ts it drops
# `fetchBodies` and reports `refresh` as overlapping `scheduleRefresh`. TS
# complexity is therefore measured with ccn.mjs (TypeScript compiler AST);
# lizard is kept for Python, where its function boundaries are correct.
set -euo pipefail

OUT=${OUT:-personA/results}
mkdir -p "$OUT"

test "$(git rev-parse HEAD)" = bf2323b3021c9d3db7a31e1e7d61068c3f704497 \
  || { echo "not at the pinned commit"; exit 1; }

# Tools (one-off): pip install lizard==1.24.1
#                  npm i jscpd@5.4.1 madge@8.0.0 typescript@5.9.3

# M1 – cyclomatic complexity and function length
lizard --csv plugins -l python > "$OUT/m1.csv"
node personA/measure/ccn.mjs \
  mods/agents-md/hooks mods/diff/hooks mods/sec-default/hooks \
  mods/telemetry/hooks scripts > "$OUT/m1ts.csv"
python personA/measure/lizard_summary.py "$OUT/m1.csv"
python personA/measure/ccn_summary.py "$OUT/m1ts.csv"

# M2 – coupling (fan-in / fan-out); self-loops from `export * as default from '.'` are dropped
for m in diff sec-default telemetry agents-md; do
  madge --extensions ts --ts-config mods/tsconfig.json --json "mods/$m/hooks" > "$OUT/m2-$m.json"
done
python personA/measure/fan.py "$OUT" diff sec-default telemetry agents-md

# M3 – duplication (≥50 tokens)
for t in plugins scripts mods; do
  jscpd "$t" --format "typescript,tsx,python" \
    --ignore "**/types/claude-code.d.ts,**/node_modules/**" \
    --min-tokens 50 --reporters json --output "$OUT/m3-$t" --silent
done

# M4 – tests (pass/fail per mod; the runner has no coverage option)
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
claude --version
for m in agents-md diff sec-default telemetry; do
  claude plugin test "mods/$m" > "$OUT/m4-$m.log" 2>&1 || true
  tail -3 "$OUT/m4-$m.log"
done
