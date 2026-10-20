"""
M5 validity check: who actually closed the bug issues?

m5_process_metrics.py uses "carries a stale/duplicate label" as a proxy for "closed by
automation". This script checks the proxy: it samples closed issues from m5_bug_issues.csv
(stratified by closure reason, fixed random seed) and reads each issue's event log to see
which account performed the closing event and whether it is a Bot account.

Usage (Git Bash, after `m5_process_metrics.py run` has produced m5_bug_issues.csv):
    export GITHUB_TOKEN=<your token>
    python ../recon/m5_validate_closers.py

Python 3.10+, standard library only. Writes m5_closers_sample.csv next to this script.
"""
import csv
import json
import os
import pathlib
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

REPO = "anthropics/claude-code"
PER_REASON = 25            # sample size per closure reason
SEED = 42                  # fixed seed so the sample is reproducible
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = pathlib.Path(__file__).resolve().parent


def get(url):
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "capstone-m5-validate"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                wait = int(e.headers.get("Retry-After") or 60)
                print(f"  rate limited, sleeping {wait}s", file=sys.stderr)
                time.sleep(min(wait, 900))
                continue
            if e.code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("giving up on " + url)


def closing_event(number):
    """Return the LAST 'closed' event of the issue (an issue can be reopened and closed again)."""
    last, page = None, 1
    while page <= 5:
        events = get(f"https://api.github.com/repos/{REPO}/issues/{number}/events?per_page=100&page={page}")
        if not events:
            break
        for ev in events:
            if ev.get("event") == "closed":
                last = ev
        if len(events) < 100:
            break
        page += 1
    return last


def main():
    if not TOKEN:
        print("Set GITHUB_TOKEN first (export GITHUB_TOKEN=...).")
        sys.exit(1)
    src = OUT / "m5_bug_issues.csv"
    rows = [r for r in csv.DictReader(open(src, encoding="utf-8")) if r["closed_at"]]
    by_reason = defaultdict(list)
    for r in rows:
        by_reason[r["state_reason"] or "unknown"].append(r)

    rng = random.Random(SEED)
    sample = []
    for reason in sorted(by_reason):
        pool = sorted(by_reason[reason], key=lambda r: int(r["number"]))
        sample += [(reason, r) for r in rng.sample(pool, min(PER_REASON, len(pool)))]

    print(f"Sampling {len(sample)} closed bug issues (seed {SEED}, up to {PER_REASON} per closure reason)")
    results = []
    for i, (reason, r) in enumerate(sample, 1):
        ev = closing_event(int(r["number"]))
        if ev is None:
            actor, atype, via = "", "no-closed-event", ""
        else:
            a = ev.get("actor") or {}
            actor, atype = a.get("login", ""), a.get("type", "")
            via = "commit" if ev.get("commit_id") else ""
        results.append([r["number"], reason, actor, atype, via, r["labels"]])
        if i % 15 == 0:
            print(f"  checked {i}/{len(sample)}", file=sys.stderr)
        time.sleep(0.3)

    with open(OUT / "m5_closers_sample.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["number", "state_reason", "closer_login", "closer_type", "closed_via_commit", "labels"])
        w.writerows(results)

    print("\nWho closed them? (closure reason x account type)")
    for reason in sorted(by_reason):
        c = Counter(r[3] for r in results if r[1] == reason)
        total = sum(c.values())
        parts = ", ".join(f"{k or 'unknown'}={v}" for k, v in c.most_common())
        print(f"  {reason:12s} n={total:3d}: {parts}")
    print("\nMost frequent closing accounts:")
    for (login, atype), n in Counter((r[2], r[3]) for r in results).most_common(8):
        print(f"  {n:3d}  {login or '(none)'}  [{atype or 'unknown'}]")


if __name__ == "__main__":
    main()
