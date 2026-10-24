# process metrics for the project health section
# reads commits.csv (only for the cutoff), pull_requests.csv, issues.csv and issue_sample.csv
# run: python process_metrics.py   -> results in analysis2/process_summary.txt
#
# everything is measured at commit bf2323b, like the rest of the report:
# - only pull requests and issues created up to the date of that commit are used
# - a pull request or issue that was merged/closed after that date counts as still open
# limitation: labels and comment counts are what github showed on the day we collected the data,
# we can't go back in time for those.
# the newcomer return rate metric is calculated in contributor_an.py, because it needs the contributor table.

import os
import sys
import pandas as pd

data_folder = "data"
out_folder = "analysis2"
os.makedirs(out_folder, exist_ok=True)

out = open(os.path.join(out_folder, "process_summary.txt"), "w", encoding="utf-8")
sys.stdout = out  # all prints go to the file

cutoff_sha = "bf2323b"
bot_list = ["actions-user"]
staff_roles = ["MEMBER", "OWNER", "COLLABORATOR"]  # author_association values that mean "part of the org"


def is_bot(login, acc_type):
    return acc_type == "Bot" or login.endswith("[bot]") or login in bot_list


def pct(part, whole):
    return round(100 * part / max(whole, 1), 1)


def to_date(column):
    # empty strings become NaT (no date)
    return pd.to_datetime(column.replace("", None), utc=True)


# ---------------- 0. cutoff ----------------
commits = pd.read_csv(os.path.join(data_folder, "commits.csv"), dtype=str, keep_default_na=False)
cutoff_row = commits.index[commits["sha"].str.startswith(cutoff_sha)][0]
cutoff_date = pd.to_datetime(commits.loc[cutoff_row, "date"], utc=True)
print("measured at commit", commits.loc[cutoff_row, "sha"], "made on", cutoff_date)
print()


# ---------------- 1. pull requests ----------------
prs = pd.read_csv(os.path.join(data_folder, "pull_requests.csv"), dtype=str, keep_default_na=False)
prs = prs[[not is_bot(l, t) for l, t in zip(prs["author_login"], prs["author_type"])]]

prs["created"] = pd.to_datetime(prs["created_at"], utc=True)
prs["closed"] = to_date(prs["closed_at"])
prs["merged"] = to_date(prs["merged_at"])
prs = prs[prs["created"] <= cutoff_date].copy()
# things that happened after the cutoff did not happen yet
prs.loc[prs["closed"] > cutoff_date, "closed"] = pd.NaT
prs.loc[prs["merged"] > cutoff_date, "merged"] = pd.NaT
prs["group"] = ["staff" if a in staff_roles else "outside" for a in prs["author_association"]]

print("=== PULL REQUESTS ===")
print("total prs (no bots):", len(prs))
for group in ["staff", "outside"]:
    g = prs[prs["group"] == group]
    merged = g["merged"].notna().sum()
    closed_not_merged = (g["closed"].notna() & g["merged"].isna()).sum()
    still_open = g["closed"].isna().sum()
    print(group, "- prs:", len(g), " authors:", g["author_login"].nunique())
    print("   merged:", merged, "(" + str(pct(merged, len(g))) + "%)",
          " closed without merge:", closed_not_merged, "(" + str(pct(closed_not_merged, len(g))) + "%)",
          " still open:", still_open, "(" + str(pct(still_open, len(g))) + "%)")

    days_to_merge = (g["merged"] - g["created"]).dt.total_seconds() / 86400
    days_to_close = (g["closed"] - g["created"])[g["merged"].isna()].dt.total_seconds() / 86400
    print("   median days to merge:", round(days_to_merge.median(), 1),
          " median days to close without merge:", round(days_to_close.median(), 1))
print("association values:", prs["author_association"].value_counts().to_dict())
print()


# ---------------- 2. issue resolution ----------------
issues = pd.read_csv(os.path.join(data_folder, "issues.csv"), dtype=str, keep_default_na=False)
issues["created"] = pd.to_datetime(issues["created_at"], utc=True)
issues = issues[issues["created"] <= cutoff_date].copy()
all_issues = issues.copy()  # with bot issues, needed for the sample weights below
issues = issues[[not is_bot(l, t) for l, t in zip(issues["author_login"], issues["author_type"])]].copy()

issues["closed"] = to_date(issues["closed_at"])
issues.loc[issues["closed"] > cutoff_date, "closed"] = pd.NaT
issues["is_closed"] = issues["closed"].notna()
# the close reason only counts for issues that were already closed at the cutoff
issues.loc[~issues["is_closed"], "state_reason"] = ""
issues["comments"] = issues["comments"].astype(int)

n = len(issues)
n_closed = issues["is_closed"].sum()
print("=== ISSUES ===")
print("total issues (no bots):", n)
print("closed:", n_closed, "(" + str(pct(n_closed, n)) + "%)")
print("close reasons (closed issues only):")
reasons = issues[issues["is_closed"]]["state_reason"].replace("", "unknown").value_counts()
for reason, count in reasons.items():
    print("  ", reason, count, "(" + str(pct(count, reasons.sum())) + "%)")

days_to_close = (issues["closed"] - issues["created"]).dt.total_seconds() / 86400
print("median days to close:", round(days_to_close.median(), 1), " 75%:", round(days_to_close.quantile(0.75), 1))
for reason in ["completed", "not_planned", "duplicate"]:
    d = days_to_close[issues["state_reason"] == reason]
    if len(d) > 0:
        print("   median days to close as", reason + ":", round(d.median(), 1))

# comments column = number of comments on the issue (incl. bot comments!)
print("issues with 0 comments:", (issues["comments"] == 0).sum(),
      "(" + str(round(100 * (issues["comments"] == 0).mean(), 1)) + "%)")
print("average comments per issue:", round(issues["comments"].mean(), 2), " median:", issues["comments"].median())

# labels, e.g. is there anything for newcomers
all_labels = issues["labels"].str.split("; ").explode()
all_labels = all_labels[all_labels != ""]
print("issues without any label:", (issues["labels"] == "").sum())
stale = issues["labels"].str.split("; ").apply(lambda labels: "stale" in labels).sum()
print("issues with the stale label:", stale, "(" + str(pct(stale, n)) + "%)")
print("top labels:")
print(all_labels.value_counts().head(15).to_string())
print("labels with 'good first' or 'help wanted' in the name:",
      all_labels[all_labels.str.lower().str.contains("good first|help wanted")].value_counts().to_dict())
print()


# ---------------- 3. who closes issues (sample) ----------------
sample = pd.read_csv(os.path.join(data_folder, "issue_sample.csv"), dtype=str, keep_default_na=False)
sample_before = len(sample)
sample = sample[pd.to_datetime(sample["created_at"], utc=True) <= cutoff_date].copy()
# issues closed after the cutoff were still open at the cutoff
closed_later = (sample["closed_at"] != "") & (to_date(sample["closed_at"]) > cutoff_date)
sample.loc[closed_later, "state"] = "open"
sample.loc[closed_later, "state_reason"] = ""
# the number of issues per month has to be counted again, because the last month is now shorter
sample["month_population"] = sample["stratum"].map(all_issues["created_at"].str[:7].value_counts())

closed_sample = sample[sample["state"] == "closed"].copy()
closed_sample["closed_by_bot"] = [is_bot(l, t) for l, t in zip(closed_sample["closed_by_login"], closed_sample["closed_by_type"])]
closed_sample["closed_by_author"] = closed_sample["closed_by_login"] == closed_sample["author_login"]

print("=== WHO CLOSES ISSUES (sample of", len(sample), "issues,", len(closed_sample), "closed) ===")
print("sampled issues opened after the cutoff (left out):", sample_before - len(sample),
      " sampled issues closed after the cutoff (counted as open):", closed_later.sum())
print("sample size per month:", sample["stratum"].value_counts().sort_index().to_dict())
print("closed by bot:", closed_sample["closed_by_bot"].sum(),
      " by issue author:", closed_sample["closed_by_author"].sum(),
      " by someone else:", (~closed_sample["closed_by_bot"] & ~closed_sample["closed_by_author"]).sum())
print("unweighted share closed by bot:", round(100 * closed_sample["closed_by_bot"].mean(), 1), "%")

# weighted: every month counts as much as it had issues (see sampling section)
monthly = closed_sample.groupby("stratum").agg(bot_share=("closed_by_bot", "mean"))
pop = sample.groupby("stratum")["month_population"].first().astype(int)
monthly["population"] = pop
weighted = (monthly["bot_share"] * monthly["population"]).sum() / monthly["population"].sum()
print("weighted share closed by bot:", round(100 * weighted, 1), "%")
print("per month:")
print((monthly["bot_share"] * 100).round(1).to_string())
print("who closed (top 10):")
print(closed_sample["closed_by_login"].value_counts().head(10).to_string())
print()

# ---------------- 4. numbers for the qualitative analysis (sample) ----------------
# we pick the examples for the qualitative analysis from the sample, so we print the groups and the top issues per group
sample["reactions_total"] = sample["reactions_total"].astype(int)
sample["comments"] = sample["comments"].astype(int)
sample["created"] = pd.to_datetime(sample["created_at"], utc=True)
sample["closed"] = to_date(sample["closed_at"])
sample.loc[sample["state"] == "open", "closed"] = pd.NaT
# how long the issue was open: until it was closed, or until the cutoff if it is still open
sample["days_open"] = ((sample["closed"].fillna(cutoff_date) - sample["created"]).dt.total_seconds() / 86400).round(0)
sample["closed_by_bot"] = [s == "closed" and is_bot(l, t) for s, l, t in
                           zip(sample["state"], sample["closed_by_login"], sample["closed_by_type"])]
sample["label_list"] = sample["labels"].str.split("; ")

groups = {
    "closed by a bot as not planned": sample[sample["closed_by_bot"] & (sample["state_reason"] == "not_planned")],
    "closed by a bot as duplicate": sample[sample["closed_by_bot"] & (sample["state_reason"] == "duplicate")],
    "still open": sample[sample["state"] == "open"],
}
print("=== SAMPLE GROUPS FOR THE QUALITATIVE ANALYSIS ===")
columns = ["number", "reactions_total", "comments", "days_open", "closed_by_login", "labels"]
for name, g in groups.items():
    print(name + ":", len(g), "issues, top 3 by reactions:")
    print(g.sort_values("reactions_total", ascending=False, kind="stable")[columns].head(3).to_string(index=False))
closed_all = sample[sample["state"] == "closed"]
top_closed = closed_all.sort_values("reactions_total", ascending=False, kind="stable").iloc[0]
print("most reactions of all closed sampled issues: #" + top_closed["number"], "with", top_closed["reactions_total"])
top_all = sample.sort_values("reactions_total", ascending=False, kind="stable").iloc[0]
print("most reactions of all sampled issues: #" + top_all["number"], "with", top_all["reactions_total"])
print()

# issues that were triaged as reproducible bugs
repro = sample[sample["label_list"].apply(lambda labels: "has repro" in labels)]
repro_bot_np = (repro["closed_by_bot"] & (repro["state_reason"] == "not_planned")).sum()
repro_done = ((repro["state"] == "closed") & (repro["state_reason"] == "completed")).sum()
print("sampled issues labelled has repro:", len(repro))
print("  closed by a bot as not planned:", repro_bot_np, "(" + str(pct(repro_bot_np, len(repro))) + "%)")
print("  closed as completed:", repro_done, "(" + str(pct(repro_done, len(repro))) + "%)")

# popular open issues
popular = groups["still open"][groups["still open"]["reactions_total"] >= 10]
print("open sampled issues with 10+ reactions:", len(popular), " of them older than 90 days:", (popular["days_open"] > 90).sum())
print()

# the three issues we discuss in the qualitative analysis
print("chosen examples:")
chosen = sample[sample["number"].isin(["13183", "13738", "14280"])]
print(chosen[["number", "created_at", "closed_at", "state", "state_reason", "closed_by_login",
              "days_open", "reactions_total", "comments", "labels"]].to_string(index=False))
print()

out.close()
sys.stdout = sys.__stdout__
print("done, see", os.path.join(out_folder, "process_summary.txt"))