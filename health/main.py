"""
Collects GitHub activity data for the project-health analysis of anthropics/claude-code.

Output (CSV files in ./data/):
  commits.csv        all commits on the default branch in the period
  pull_requests.csv  all pull requests created in the period
  issues.csv         all issues (not PRs) created in the period
  reviews.csv        all reviews on the pull requests created in the period
  issue_sample.csv   stratified random sample of issues (25 per month), incl. who closed them

Every row stores the login of the account and its GitHub account type ("User" or "Bot").
Pull requests, issues and reviews also store the author_association
(e.g. MEMBER, CONTRIBUTOR, NONE). We need these to filter out bots and to tell
staff apart from outside contributors.

How to run:
  pip install requests
  set the GITHUB_TOKEN environment variable to a personal access token
  python main.py

If a CSV file already exists it is skipped. So if the script crashes halfway
(for example because of a network error) you can just run it again.

Note: this script collects everything up to the moment it is run. The analysis
scripts (contributor_an.py, process_metrics.py) then cut the data off at
commit bf2323b, which is the commit used in the rest of the report.
"""

import csv
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

# ------------------------------------------------------------ settings

OWNER = "anthropics"
REPO = "claude-code"

END = datetime.now(timezone.utc)      # the period ends now
START = END - timedelta(days=365)     # and starts one year earlier

SAMPLE_PER_MONTH = 25                 # number of issues we sample per month
RANDOM_SEED = 42                      # fixed seed so the sample is the same every time
BODY_CHARS = 500                      # how many characters of a text body we keep

OUT_DIR = "data"
API = "https://api.github.com"

# ------------------------------------------------------------ connecting to github

# the token is read from an environment variable so it is never stored in the code
TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    sys.exit("Set the GITHUB_TOKEN environment variable first.")

session = requests.Session()
session.headers.update({
    "Authorization": "Bearer " + TOKEN,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})


def get(url, params=None):
    # does a GET request, tries again on errors and waits when the rate limit is hit
    for attempt in range(6):
        try:
            r = session.get(url, params=params, timeout=60)
        except requests.RequestException as e:
            print(f"  network error ({e}), retrying...")
            time.sleep(10 * (attempt + 1))
            continue

        if r.status_code == 200:
            return r

        # rate limit (403 or 429)
        if r.status_code == 403 or r.status_code == 429:
            if r.headers.get("X-RateLimit-Remaining") == "0":
                # we used up all requests, wait until github resets the limit
                reset_time = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset_time - time.time(), 0) + 5
                print(f"  rate limit reached, waiting {wait / 60:.1f} minutes...")
                time.sleep(wait)
                continue
            # secondary rate limit: github tells us how long to wait
            retry_after = int(r.headers.get("Retry-After", 60))
            print(f"  secondary rate limit, waiting {retry_after} s...")
            time.sleep(retry_after)
            continue

        # server errors are usually temporary, so just try again
        if r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue

        # any other error (e.g. 404) stops the script
        r.raise_for_status()

    raise RuntimeError(f"Giving up on {url}")


def get_all_items(url, params=None):
    # github returns lists in pages of max 100 items.
    # this goes through all pages and gives back the items one by one.
    # it uses yield, so the caller can stop early and we don't download pages we don't need.
    if params is None:
        params = {}
    else:
        params = dict(params)  # copy, so we don't change the dict of the caller
    if "per_page" not in params:
        params["per_page"] = 100

    page = 0
    while url:
        r = get(url, params)
        page = page + 1
        if page % 20 == 0:
            print(f"  ...page {page} (rate limit left: {r.headers.get('X-RateLimit-Remaining')})")

        for item in r.json():
            yield item

        # the link to the next page is in the response headers
        if "next" in r.links:
            url = r.links["next"].get("url")
        else:
            url = None
        params = None  # the next url already has all the parameters in it


def parse_time(value):
    # github dates look like 2025-10-15T16:47:24Z
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def in_period(value):
    t = parse_time(value)
    if t is None:
        return False
    return START <= t <= END


def user_fields(user):
    # returns the login and account type of a user, deleted accounts give None
    if not user:
        return "", ""
    return user.get("login", ""), user.get("type", "")


def short(text):
    # keeps only the start of a text and puts it on one line
    if not text:
        text = ""
    text = text.replace("\r", " ").replace("\n", " ")
    return text[:BODY_CHARS]


def write_csv(name, fieldnames, rows):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  saved {len(rows)} rows to {path}")


def read_csv(name):
    with open(os.path.join(OUT_DIR, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def column_names(rows, default):
    # the columns of the csv are the keys of the first row
    if len(rows) > 0:
        return list(rows[0].keys())
    return [default]


# ------------------------------------------------------------ 1. commits

COAUTHOR = re.compile(r"Co-authored-by:\s*(.+)", re.IGNORECASE)


def collect_commits():
    print("Commits...")
    rows = []
    url = f"{API}/repos/{OWNER}/{REPO}/commits"
    params = {"since": START.isoformat(), "until": END.isoformat()}

    for c in get_all_items(url, params):
        login, acc_type = user_fields(c.get("author"))

        info = c["commit"]["author"]
        if not info:
            info = {}
        message = c["commit"]["message"]
        if not message:
            message = ""

        co_authors = []
        for name in COAUTHOR.findall(message):
            co_authors.append(name.strip())

        rows.append({
            "sha": c["sha"],
            "date": info.get("date", ""),
            "author_login": login,                       # empty if the email is not linked to an account
            "author_type": acc_type,
            "author_name": info.get("name", ""),
            "author_email": info.get("email", ""),
            "parents": len(c.get("parents", [])),        # 2 or more means merge commit
            "message_first_line": message.split("\n")[0][:200],
            "co_authors": "; ".join(co_authors),
            "url": c["html_url"],
        })

    write_csv("commits.csv", column_names(rows, "sha"), rows)


# ------------------------------------------------------------ 2. pull requests

def collect_pull_requests():
    print("Pull requests...")
    rows = []
    url = f"{API}/repos/{OWNER}/{REPO}/pulls"
    params = {"state": "all", "sort": "created", "direction": "desc"}

    for pr in get_all_items(url, params):
        created = parse_time(pr["created_at"])
        if created > END:
            continue
        if created < START:
            break  # newest first, so all the next ones are too old as well

        login, acc_type = user_fields(pr.get("user"))
        rows.append({
            "number": pr["number"],
            "title": pr["title"][:200],
            "author_login": login,
            "author_type": acc_type,
            "author_association": pr.get("author_association", ""),
            "created_at": pr["created_at"],
            "closed_at": pr.get("closed_at") or "",
            "merged_at": pr.get("merged_at") or "",
            "state": pr["state"],
            "draft": pr.get("draft", False),
            "body_start": short(pr.get("body")),
            "url": pr["html_url"],
        })

    write_csv("pull_requests.csv", column_names(rows, "number"), rows)


# ------------------------------------------------------------ 3. issues

def collect_issues():
    print("Issues (this is the big one)...")
    rows = []
    url = f"{API}/repos/{OWNER}/{REPO}/issues"
    # "since" looks at the last update, so we still have to check the creation date ourselves
    params = {"state": "all", "since": START.isoformat(), "sort": "created", "direction": "asc"}

    for it in get_all_items(url, params):
        if "pull_request" in it:
            continue  # the issues endpoint also returns PRs, we already have those
        if not in_period(it["created_at"]):
            continue

        login, acc_type = user_fields(it.get("user"))

        label_names = []
        for label in it.get("labels", []):
            label_names.append(label["name"])

        reactions = it.get("reactions")
        if not reactions:
            reactions = {}

        rows.append({
            "number": it["number"],
            "title": it["title"][:200],
            "author_login": login,
            "author_type": acc_type,
            "author_association": it.get("author_association", ""),
            "created_at": it["created_at"],
            "closed_at": it.get("closed_at") or "",
            "state": it["state"],
            "state_reason": it.get("state_reason") or "",   # completed / not_planned / duplicate
            "labels": "; ".join(label_names),
            "comments": it.get("comments", 0),
            "reactions_total": reactions.get("total_count", 0),
            "body_start": short(it.get("body")),
            "url": it["html_url"],
        })

    write_csv("issues.csv", column_names(rows, "number"), rows)


# ------------------------------------------------------------ 4. reviews

def collect_reviews():
    print("Reviews (one request per pull request)...")
    prs = read_csv("pull_requests.csv")
    rows = []
    count = 0

    for pr in prs:
        count = count + 1
        url = f"{API}/repos/{OWNER}/{REPO}/pulls/{pr['number']}/reviews"

        for rv in get_all_items(url):
            if not rv.get("submitted_at"):
                continue  # review that was started but never submitted

            login, acc_type = user_fields(rv.get("user"))
            rows.append({
                "pr_number": pr["number"],
                "pr_author": pr["author_login"],
                "reviewer_login": login,
                "reviewer_type": acc_type,
                "reviewer_association": rv.get("author_association", ""),
                "state": rv["state"],              # APPROVED / CHANGES_REQUESTED / COMMENTED
                "submitted_at": rv["submitted_at"],
                "body_start": short(rv.get("body")),
                "url": rv["html_url"],
            })

        if count % 50 == 0:
            print(f"  {count}/{len(prs)} pull requests done")

    write_csv("reviews.csv", column_names(rows, "pr_number"), rows)


# ------------------------------------------------------------ 5. stratified issue sample

def collect_issue_sample():
    print(f"Stratified issue sample ({SAMPLE_PER_MONTH} per month)...")
    issues = read_csv("issues.csv")

    # put the issues in groups by the month they were opened (these are the strata)
    by_month = {}
    for it in issues:
        month = it["created_at"][:7]   # e.g. "2025-10"
        if month not in by_month:
            by_month[month] = []
        by_month[month].append(it)

    rng = random.Random(RANDOM_SEED)
    sample = []
    for month in sorted(by_month):
        group = by_month[month]
        how_many = min(SAMPLE_PER_MONTH, len(group))
        picked = rng.sample(group, how_many)
        for it in picked:
            row = dict(it)  # copy so we don't change the original issue
            row["stratum"] = month
            row["month_population"] = len(group)
            sample.append(row)

    # who closed an issue is only given by the endpoint for a single issue
    count = 0
    for row in sample:
        count = count + 1
        row["closed_by_login"] = ""
        row["closed_by_type"] = ""
        if row["state"] == "closed":
            data = get(f"{API}/repos/{OWNER}/{REPO}/issues/{row['number']}").json()
            login, acc_type = user_fields(data.get("closed_by"))
            row["closed_by_login"] = login
            row["closed_by_type"] = acc_type
        if count % 50 == 0:
            print(f"  {count}/{len(sample)} sampled issues done")

    write_csv("issue_sample.csv", column_names(sample, "number"), sample)


# ------------------------------------------------------------ main

# (file name, function that makes it). The order matters:
# reviews need pull_requests.csv and the sample needs issues.csv
STEPS = [
    ("commits.csv", collect_commits),
    ("pull_requests.csv", collect_pull_requests),
    ("issues.csv", collect_issues),
    ("reviews.csv", collect_reviews),
    ("issue_sample.csv", collect_issue_sample),
]

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Repository: {OWNER}/{REPO}")
    print(f"Period: {START:%Y-%m-%d} to {END:%Y-%m-%d} (collected {datetime.now():%Y-%m-%d %H:%M})\n")

    for filename, step in STEPS:
        if os.path.exists(os.path.join(OUT_DIR, filename)):
            print(f"{filename} already exists, skipping.")
            continue
        step()

    print("\nDone. Write down the collection date above in your report.")