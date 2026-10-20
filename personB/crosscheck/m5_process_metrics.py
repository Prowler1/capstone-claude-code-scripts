"""
M5: process metrics for anthropics/claude-code from the GitHub Search API.

Usage (Git Bash):
    export GITHUB_TOKEN=<your token>     # never hardcode it in the script
    python m5_process_metrics.py labels  # step 1: discover the real label names
    python m5_process_metrics.py run     # step 2: compute the metrics

Python 3.10+, standard library only.
Writes m5_labels.csv (labels mode) and m5_bug_issues.csv (run mode) next to this script.

Cohort definition: all issues CREATED between WINDOW_START and WINDOW_END (inclusive)
that carry a bug label. The numbers depend on the day you run the script (issues keep
closing), so record the printed snapshot time in your footnote.
"""
import csv
import json
import math
import os
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------------ settings
REPO = "anthropics/claude-code"
WINDOW_START = "2026-04-01"            # issues created in [start, end]
WINDOW_END = "2026-06-30"
BUG_LABELS = ["bug"]                   # EDIT after running `labels` mode
FEATURE_LABELS = ["enhancement"]       # EDIT after running `labels` mode
BOT_CLOSE_LABELS = ["stale", "duplicate", "autoclose", "needs-repro"]
SLEEP = 2.2                            # search API allows 30 requests/minute
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = pathlib.Path(__file__).resolve().parent
UTC = timezone.utc


# ------------------------------------------------------------------ plumbing
def api(path, params=None):
    url = "https://api.github.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "capstone-m5-metrics"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r), r.headers
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                wait = int(e.headers.get("Retry-After") or 0)
                if not wait:
                    reset = e.headers.get("X-RateLimit-Reset")
                    if reset and e.headers.get("X-RateLimit-Remaining") == "0":
                        wait = max(int(reset) - int(time.time()), 1) + 1
                    else:
                        wait = 60
                print(f"  rate limited, sleeping {wait}s", file=sys.stderr)
                time.sleep(min(wait, 900))
                continue
            if e.code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("giving up on " + url)


def search(q, per_page=100, page=1):
    time.sleep(SLEEP)
    data, _ = api("/search/issues", {"q": q, "per_page": per_page, "page": page,
                                     "sort": "created", "order": "asc"})
    return data


def q_base(extra=""):
    return f"repo:{REPO} is:issue {extra}".strip()


def label_q(labels):
    """label:"a","b" means a OR b in GitHub search."""
    return "label:" + ",".join(f'"{l}"' for l in labels)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def window():
    a = datetime.fromisoformat(WINDOW_START).replace(tzinfo=UTC)
    b = datetime.fromisoformat(WINDOW_END).replace(tzinfo=UTC) + timedelta(hours=23, minutes=59, seconds=59)
    return a, b


def fetch_range(lq, a, b, out):
    """Fetch every matching issue created in [a, b]; split the range if >1000 hits
    (the search API never returns more than 1000 results per query)."""
    q = q_base(f"{lq} created:{iso(a)}..{iso(b)}")
    d = search(q)
    total = d["total_count"]
    if total == 0:
        return
    if total > 1000 and a < b:
        mid = (a + (b - a) / 2).replace(microsecond=0)
        fetch_range(lq, a, mid, out)
        fetch_range(lq, mid + timedelta(seconds=1), b, out)
        return
    if total > 1000:
        print(f"WARNING: >1000 issues in a single second {iso(a)}; truncated", file=sys.stderr)
    items = list(d["items"])
    for p in range(2, math.ceil(min(total, 1000) / 100) + 1):
        items += search(q, page=p)["items"]
    out.extend(items)
    print(f"  fetched {len(items):4d} issues for {iso(a)} .. {iso(b)}", file=sys.stderr)


# --------------------------------------------------------------- labels mode
def mode_labels():
    names, page = [], 1
    while True:
        d, _ = api(f"/repos/{REPO}/labels", {"per_page": 100, "page": page})
        if not d:
            break
        names += [x["name"] for x in d]
        page += 1
    win = f"created:{WINDOW_START}..{WINDOW_END}"
    total = search(q_base(win), per_page=1)["total_count"]
    print(f"{len(names)} labels in repo; {total} issues created {WINDOW_START}..{WINDOW_END}")
    rows = []
    for i, n in enumerate(names, 1):
        c = search(q_base(f'label:"{n}" {win}'), per_page=1)["total_count"]
        rows.append((c, n))
        if i % 20 == 0:
            print(f"  counted {i}/{len(names)} labels", file=sys.stderr)
    rows.sort(reverse=True)
    with open(OUT / "m5_labels.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "issues_in_window"])
        w.writerows([(n, c) for c, n in rows])
    print("top labels (issues in window):")
    for c, n in rows[:30]:
        print(f"  {c:6d}  {n}")


# ------------------------------------------------------------------ run mode
def pct(x, y):
    return f"{100 * x / y:.1f}%" if y else "n/a"


def p90(sorted_vals):
    return sorted_vals[math.ceil(0.9 * len(sorted_vals)) - 1]


def summarize(title, days):
    days = sorted(days)
    if not days:
        print(f"  {title}: no closed issues")
        return
    print(f"  {title}: n={len(days)}, median={statistics.median(days):.1f} d, p90={p90(days):.1f} d")


def mode_run():
    snapshot = datetime.now(UTC)
    a, b = window()
    win = f"created:{WINDOW_START}..{WINDOW_END}"
    bug_q, feat_q = label_q(BUG_LABELS), label_q(FEATURE_LABELS)

    def count(extra):
        return search(q_base(f"{extra} {win}"), per_page=1)["total_count"]

    print(f"Snapshot (UTC): {iso(snapshot)}")
    print(f"Repo: {REPO}; cohort: issues created {WINDOW_START}..{WINDOW_END}")
    print(f"Bug labels: {BUG_LABELS}; feature labels: {FEATURE_LABELS}; bot-close labels: {BOT_CLOSE_LABELS}")

    n_all = count("")
    n_bug = count(bug_q)
    n_feat = count(feat_q)
    n_both = count(f"{bug_q} {feat_q}")
    n_bug_open = count(f"{bug_q} is:open")
    print("\nLabel distribution (counts from search total_count):")
    print(f"  all issues: {n_all}")
    print(f"  bug-labelled: {n_bug} ({pct(n_bug, n_all)})")
    print(f"  feature-labelled: {n_feat} ({pct(n_feat, n_all)})")
    print(f"  both bug and feature: {n_both}")
    print(f"  neither: {n_all - n_bug - n_feat + n_both} ({pct(n_all - n_bug - n_feat + n_both, n_all)})")
    print(f"  bug-to-feature ratio: {n_bug / n_feat:.2f}" if n_feat else "  no feature issues")
    print(f"\nOpen-bug ratio: {n_bug_open}/{n_bug} = {pct(n_bug_open, n_bug)}")

    print("\nFetching every bug issue in the window (this takes a while) ...", file=sys.stderr)
    items = []
    fetch_range(bug_q, a, b, items)
    by_num = {it["number"]: it for it in items}
    print(f"\nFetched {len(by_num)} unique bug issues (search count said {n_bug}); "
          f"mismatch means issues changed during the run or the range was truncated.")

    rows, closed_days = [], []
    reason_days, bot_days = {}, []
    for it in by_num.values():
        labels = [l["name"] for l in it["labels"]]
        created = parse(it["created_at"])
        closed = parse(it["closed_at"]) if it.get("closed_at") else None
        days = (closed - created).total_seconds() / 86400 if closed else None
        reason = it.get("state_reason")
        is_bot = bool(closed) and any(l in BOT_CLOSE_LABELS for l in labels)
        rows.append([it["number"], it["created_at"], it.get("closed_at") or "", it["state"],
                     reason or "", "|".join(labels), f"{days:.3f}" if days is not None else "", int(is_bot)])
        if days is not None:
            closed_days.append(days)
            reason_days.setdefault(reason or "unknown", []).append(days)
            if is_bot:
                bot_days.append(days)

    with open(OUT / "m5_bug_issues.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["number", "created_at", "closed_at", "state", "state_reason",
                    "labels", "days_to_close", "closed_with_bot_label"])
        w.writerows(rows)

    n = len(by_num)
    print(f"\nTime to close, bug issues (closed ones only; open issues are not counted):")
    print(f"  closed: {len(closed_days)}/{n} = {pct(len(closed_days), n)}")
    summarize("all closed bugs", closed_days)
    for r, d in sorted(reason_days.items()):
        summarize(f"closed as '{r}'", d)
    summarize("closed with a bot label", bot_days)
    print(f"  share of ALL bugs closed within 7 days:  {pct(sum(d <= 7 for d in closed_days), n)}")
    print(f"  share of ALL bugs closed within 30 days: {pct(sum(d <= 30 for d in closed_days), n)}")
    print(f"  share of closed bugs that carry a bot label: {pct(len(bot_days), len(closed_days))}")
    if not any(r[4] for r in rows):
        print("\nNOTE: state_reason is empty for every row; check the CSV before using that split.")


if __name__ == "__main__":
    if not TOKEN:
        print("Set GITHUB_TOKEN first (export GITHUB_TOKEN=...). Unauthenticated search is far too slow.")
        sys.exit(1)
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "labels":
        mode_labels()
    elif mode == "run":
        mode_run()
    else:
        print("usage: python m5_process_metrics.py labels|run")
        sys.exit(1)
