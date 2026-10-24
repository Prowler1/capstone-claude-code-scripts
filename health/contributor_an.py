# analysis for the project health section (filtering + contributors + activity)
# reads the csv files made by main.py and writes the numbers we need to analysis2/summary.txt
# run: python contributor_an.py
#
# all data is cut off at commit bf2323b, the same commit used in the rest of the report.
# commits.csv lists the commits newest first, so we keep the row of bf2323b and everything below it.
# for pull requests, issues and reviews we keep everything up to the date of that commit.

import os
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # only save the plots to files, don't open windows
import matplotlib.pyplot as plt

data_folder = "data"
out_folder = "analysis2"
os.makedirs(out_folder, exist_ok=True)

# print whole tables instead of cutting them off with "..."
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_rows", 100)

# send all prints to the summary file instead of the screen
summary_file = open(os.path.join(out_folder, "summary.txt"), "w", encoding="utf-8")
sys.stdout = summary_file

cutoff_sha = "bf2323b"

# actions-user is typed as User on github but it's a bot (see filtering section)
bot_list = ["actions-user"]
# the claude account is used by several people, so we don't count it as one person
# ghost = placeholder github uses for deleted accounts (lots of different people)
shared_accounts = ["claude", "ghost"]

# thresholds
key_share = 0.8      # key contributors = smallest group that made 80% of the accepted changes
newcomer_days = 90   # newcomer = first activity in the last 90 days
# the dormant threshold is not fixed here, it is the 90th percentile of the gaps (see below)


def pct(part, whole):
    return round(100 * part / whole, 1)


# --- load all the csv files ---
commits = pd.read_csv(os.path.join(data_folder, "commits.csv"), dtype=str, keep_default_na=False)
prs = pd.read_csv(os.path.join(data_folder, "pull_requests.csv"), dtype=str, keep_default_na=False)
issues = pd.read_csv(os.path.join(data_folder, "issues.csv"), dtype=str, keep_default_na=False)
reviews = pd.read_csv(os.path.join(data_folder, "reviews.csv"), dtype=str, keep_default_na=False)


# --- cut everything off at commit bf2323b ---
cutoff_row = commits.index[commits["sha"].str.startswith(cutoff_sha)][0]
cutoff_date = pd.to_datetime(commits.loc[cutoff_row, "date"], utc=True)
commits = commits.loc[cutoff_row:]  # the cutoff commit and all older ones

prs = prs[pd.to_datetime(prs["created_at"], utc=True) <= cutoff_date].copy()
issues = issues[pd.to_datetime(issues["created_at"], utc=True) <= cutoff_date]
reviews = reviews[pd.to_datetime(reviews["submitted_at"], utc=True) <= cutoff_date]
# a pull request that was merged after the cutoff was not merged yet at the cutoff
merged_later = (prs["merged_at"] != "") & (pd.to_datetime(prs["merged_at"].replace("", None), utc=True) > cutoff_date)
prs.loc[merged_later, "merged_at"] = ""

print("cutoff commit:", commits.loc[cutoff_row, "sha"], "made on", cutoff_date)
print("commits up to and including the cutoff:", len(commits))
print()


# --- filtering checks (section: filtering) ---
print("=== FILTERING ===")
print("account types of commit authors:", commits["author_type"].value_counts().to_dict())
print("commits without a linked account:", (commits["author_login"] == "").sum())
print("merge commits (2 parents, left out like on the github contributors page):", (commits["parents"] == "2").sum())
print()

# accounts that look like bots: type Bot, [bot] in the name or on our own list
for login in ["actions-user", "claude[bot]", "claude"]:
    c = commits[commits["author_login"] == login]
    print("account", login, "-", len(c), "commits, type:", c["author_type"].unique().tolist())
    print("   names:", c["author_name"].unique().tolist(), " emails:", c["author_email"].unique().tolist())
    print("   commit messages (first line):")
    print(c["message_first_line"].value_counts().head(5).to_string())
    months = pd.to_datetime(c["date"], utc=True).dt.strftime("%Y-%m").value_counts()
    print("   commits per month: min", months.min(), "max", months.max(), "in", len(months), "months")
    print()

# one person with several accounts / one account with several names or emails
names_per_login = commits[commits["author_login"] != ""].groupby("author_login")["author_name"].nunique()
emails_per_login = commits[commits["author_login"] != ""].groupby("author_login")["author_email"].nunique()
print("logins that commit under more than one name:", names_per_login[names_per_login > 1].to_dict())
print("logins that commit with more than one email:", emails_per_login[emails_per_login > 1].to_dict())
logins_per_email = commits[commits["author_login"] != ""].groupby("author_email")["author_login"].nunique()
logins_per_name = commits[commits["author_login"] != ""].groupby("author_name")["author_login"].nunique()
print("emails used by more than one login:", logins_per_email[logins_per_email > 1].to_dict())
print("names used by more than one login:", logins_per_name[logins_per_name > 1].to_dict())
print()


commits_with_merges = commits  # kept for the share of bot commits

# skip merge commits (2 parents), github contributors page does the same
commits = commits[commits["parents"] != "2"]
# commits without a linked account cant be counted per person
commits = commits[commits["author_login"] != ""]


# --- put everything in one table: who, type of account, when, what ---
c = pd.DataFrame({"login": commits["author_login"], "acc_type": commits["author_type"], "date": commits["date"]})
c["activity"] = "commit"

p = pd.DataFrame({"login": prs["author_login"], "acc_type": prs["author_type"], "date": prs["created_at"]})
p["activity"] = "pull_request"

i = pd.DataFrame({"login": issues["author_login"], "acc_type": issues["author_type"], "date": issues["created_at"]})
i["activity"] = "issue"

r = pd.DataFrame({"login": reviews["reviewer_login"], "acc_type": reviews["reviewer_type"], "date": reviews["submitted_at"]})
r["activity"] = "review"

# comments are not used: they could not be collected for the whole period
df = pd.concat([c, p, i, r], ignore_index=True)
df = df[df["login"] != ""]  # deleted accounts have no login
df["date"] = pd.to_datetime(df["date"], utc=True)
df["month"] = df["date"].dt.strftime("%Y-%m")
df["day"] = df["date"].dt.date

end_date = cutoff_date
print("data from", df["date"].min().date(), "to", end_date.date())
print("all activities (merge commits left out):", len(df))
print(df["activity"].value_counts())
print()


# --- remove bots ---
is_bot = (df["acc_type"] == "Bot") | df["login"].str.endswith("[bot]") | df["login"].isin(bot_list)

print("--- BOT ACTIVITY BREAKDOWN ---")
bot_df = df[is_bot]
if not bot_df.empty:
    # one row per bot, one column per activity type
    bot_breakdown = bot_df.groupby(["login", "activity"]).size().unstack(fill_value=0)
    bot_breakdown["Total"] = bot_breakdown.sum(axis=1)
    bot_breakdown = bot_breakdown.sort_values(by="Total", ascending=False, kind="stable")
    print(bot_breakdown)
else:
    print("No bot activities found.")
print()

print("activities by bots:", is_bot.sum(), "=", pct(is_bot.sum(), len(df)), "%")
bot_commits = (is_bot & (df["activity"] == "commit")).sum()
all_commits = (df["activity"] == "commit").sum()
print("commits by bots:", bot_commits, "of", all_commits, "non-merge commits =", pct(bot_commits, all_commits), "%")
print("  (counted with merge commits:", bot_commits, "of", len(commits_with_merges), "=", pct(bot_commits, len(commits_with_merges)), "%)")
print()
df = df[~is_bot]

ghost = df[df["login"] == "ghost"]
print("ghost (deleted accounts):", len(ghost), "activities in", ghost["month"].nunique(), "months")
claude_acc = df[df["login"] == "claude"]
print("claude account:", len(claude_acc), "activities", claude_acc["activity"].value_counts().to_dict())
print()


# --- activity per month (shared accounts still included here) ---
print("=== ACTIVITY ===")
print("human activities:", len(df))
for act, count in df["activity"].value_counts().items():
    print("  ", act, count, "(" + str(pct(count, len(df))) + "%)")
per_month = pd.crosstab(df["month"], df["activity"])
per_month.to_csv(os.path.join(out_folder, "activity_per_month.csv"))
print("activities per month:")
print(per_month.sum(axis=1).to_string())
print("commits per month:")
print(per_month["commit"].to_string())
print()

per_month.plot(kind="bar", stacked=True, figsize=(10, 5))
plt.title("Activity per month (no bots)")
plt.ylabel("number of activities")
plt.tight_layout()
plt.savefig(os.path.join(out_folder, "activity_per_month.png"), dpi=200)
plt.close()

# from here on only real people
people = df[~df["login"].isin(shared_accounts)]


# --- metrics per contributor ---
counts = pd.crosstab(people["login"], people["activity"])
for col in ["commit", "pull_request", "review", "issue"]:
    if col not in counts.columns:
        counts[col] = 0

contrib = counts.copy()
contrib["total"] = contrib["commit"] + contrib["pull_request"] + contrib["review"] + contrib["issue"]
contrib["code"] = contrib["commit"] + contrib["pull_request"] + contrib["review"]

# merged prs per person, opening a pr that never gets merged isnt really "key" work
merged = prs[prs["merged_at"] != ""]
merged_count = merged["author_login"].value_counts()
contrib["merged_pr"] = merged_count.reindex(contrib.index).fillna(0).astype(int)
# accepted changes = changes that really ended up in the repository
contrib["accepted"] = contrib["commit"] + contrib["merged_pr"]

grouped = people.groupby("login")
contrib["first"] = grouped["date"].min()
contrib["last"] = grouped["date"].max()
contrib["active_months"] = grouped["month"].nunique()
contrib["active_days"] = grouped["day"].nunique()

n = len(contrib)
print("=== CONTRIBUTORS ===")
print("number of contributors:", n)
print("  with code activity (commit/pr/review):", (contrib["code"] > 0).sum())
print("  only issues:", (contrib["code"] == 0).sum(), "(" + str(pct((contrib["code"] == 0).sum(), n)) + "%)")
print()


# --- distributions (to choose the thresholds) ---
print("how many activities per person:")
groups = pd.cut(contrib["total"], bins=[0, 1, 2, 5, 10, 50, 100000], labels=["1", "2", "3-5", "6-10", "11-50", ">50"])
group_counts = groups.value_counts().sort_index()
print(pd.DataFrame({"people": group_counts, "%": (100 * group_counts / n).round(1)}))
print()

print("active months per person:")
month_counts = contrib["active_months"].value_counts().sort_index()
print(pd.DataFrame({"people": month_counts, "%": (100 * month_counts / n).round(1)}))
print()

# people who open a LOT of issues, could be scripts/bots -> check them by hand
contrib["issues_per_day"] = (contrib["issue"] / contrib["active_days"]).round(1)
print("top issue openers (check if these are really humans):")
print(contrib.sort_values("issue", ascending=False, kind="stable").head(15)[["issue", "active_days", "issues_per_day"]])
print()

# how concentrated is the work? (top x people do y% of it)
# kind="stable" -> people with the same number stay in alphabetical order, so the result is the same every run
curves = {"total": "all activity",
          "code": "code activity (commits, PRs, reviews)",
          "accepted": "accepted changes (commits + merged PRs)",
          "issue": "issues opened"}
for col in curves:
    s = contrib[col].sort_values(ascending=False, kind="stable")
    s = s[s > 0]
    cum = s.cumsum() / s.sum()
    print("concentration of", col, "-", len(s), "people,", s.sum(), "in total")
    for share in [0.5, 0.8, 0.9]:
        top = (cum < share).sum() + 1
        print("  ", int(share * 100), "% done by top", top, "people")
    plt.plot(range(1, len(cum) + 1), cum.values, label=curves[col])
plt.axhline(key_share, color="grey", linestyle="--", linewidth=1)
plt.xscale("log")
plt.xlabel("number of people (most active first)")
plt.ylabel("share of activity")
plt.legend(loc="lower right", fontsize="small")
plt.title("Concentration of activity")
plt.savefig(os.path.join(out_folder, "concentration.png"), dpi=200)
plt.close()
print()

# why key contributors are based on accepted changes only
pr_authors = contrib[contrib["pull_request"] > 0]
reviewers = contrib[contrib["review"] > 0]
only_review = reviewers[(reviewers["commit"] == 0) & (reviewers["pull_request"] == 0) & (reviewers["issue"] == 0)]
print("people who opened a pr:", len(pr_authors), " of them with a merged pr:", (pr_authors["merged_pr"] > 0).sum())
print("people who reviewed:", len(reviewers), " of them did nothing else:", len(only_review),
      " of those with exactly 1 review:", (only_review["review"] == 1).sum())
print()

# new people per month
# NOTE first months look too high because people who were already active before oct 2025 also count as new there
first_month = contrib["first"].dt.strftime("%Y-%m").value_counts().sort_index()
print("new contributors per month:")
print(first_month)
print()
first_month.plot(kind="bar")
plt.title("New contributors per month")
plt.xlabel("month of first activity")
plt.tight_layout()
plt.savefig(os.path.join(out_folder, "new_per_month.png"), dpi=200)
plt.close()

# gaps between active days of the same person (for dormant threshold)
days = people[["login", "day"]].drop_duplicates().sort_values(["login", "day"])
days["day"] = pd.to_datetime(days["day"])
days["gap"] = days.groupby("login")["day"].diff().dt.days
gaps = days["gap"].dropna()
print("gaps between active days (people with 2+ days):", len(gaps), "gaps")
print("  median:", gaps.median(), " 75%:", gaps.quantile(0.75), " 90%:", gaps.quantile(0.9), " 95%:", gaps.quantile(0.95))
# 90% of the gaps are at most this long, so a longer silence is unusual
dormant_days = int(gaps.quantile(0.9))
print("  -> dormant threshold:", dormant_days, "days")
print()
gaps.clip(upper=180).plot(kind="hist", bins=36, label="gaps")
plt.axvline(dormant_days, color="red", linestyle="--", linewidth=1, label="90% of gaps (" + str(dormant_days) + " days)")
plt.legend()
plt.xlabel("days between active days (max 180)")
plt.title("Gaps between activity")
plt.savefig(os.path.join(out_folder, "gaps.png"), dpi=200)
plt.close()


# --- categories ---
ranked = contrib["accepted"].sort_values(ascending=False, kind="stable")
ranked = ranked[ranked > 0]
cum = ranked.cumsum() / ranked.sum()
num_key = (cum < key_share).sum() + 1
key_people = list(ranked.index[:num_key])

newcomer_from = end_date - pd.Timedelta(days=newcomer_days)
dormant_before = end_date - pd.Timedelta(days=dormant_days)

cats = []
for login, row in contrib.iterrows():
    if login in key_people:
        cats.append("key")
    elif row["first"] >= newcomer_from:
        cats.append("newcomer")
    elif row["last"] < dormant_before:
        # someone with only one active day never really "stopped", they just came once
        if row["active_days"] >= 2:
            cats.append("dormant")
        else:
            cats.append("one-time")
    else:
        cats.append("occasional")
contrib["category"] = cats

print("=== CATEGORIES ===")
print("key = accepted changes, newcomer =", newcomer_days, "days, dormant =", dormant_days, "days")
cat_counts = contrib["category"].value_counts()
print(pd.DataFrame({"people": cat_counts, "%": (100 * cat_counts / n).round(1)}))
print()

print("people with an accepted change:", len(ranked), " accepted changes in total:", ranked.sum())
print("key contributors:", num_key, "(the next person has", ranked.iloc[num_key] if num_key < len(ranked) else "-",
      "accepted changes, the last key person has", ranked.iloc[num_key - 1], ")")
emails = commits.groupby("author_login")["author_email"].agg(lambda e: ", ".join(sorted(set(e))))
key_table = contrib.loc[key_people, ["commit", "merged_pr", "accepted", "pull_request", "review", "issue", "active_months"]].copy()
key_table["share_of_accepted_%"] = (100 * key_table["accepted"] / ranked.sum()).round(1)
key_table["emails"] = emails.reindex(key_people).fillna("")
print(key_table)
print("accepted changes per month of the top key contributor (" + key_people[0] + "):")
top = people[(people["login"] == key_people[0]) & (people["activity"] == "commit")]
print(top["month"].value_counts().sort_index().to_string())
print()


# --- newcomers and return rate (newcomer return rate metric) ---
newcomers = contrib[contrib["category"] == "newcomer"]
print("=== NEWCOMERS AND RETURN RATE ===")
print("newcomers:", len(newcomers), " with code activity:", (newcomers["code"] > 0).sum(),
      " with an accepted change:", (newcomers["accepted"] > 0).sum())

# only people who joined more than 90 days before the end had enough time to come back
old = contrib[contrib["first"] < newcomer_from]
print("contributors whose first activity was more than", newcomer_days, "days before the end:", len(old))
print("  active on more than one day:", pct((old["active_days"] > 1).sum(), len(old)), "%")
only_issues = old[old["code"] == 0]
opened_pr = old[old["pull_request"] > 0]
accepted = old[old["accepted"] > 0]
print("  only issues:", len(only_issues), "->", pct((only_issues["active_days"] > 1).sum(), len(only_issues)), "% came back")
print("  opened a pr:", len(opened_pr), "->", pct((opened_pr["active_days"] > 1).sum(), len(opened_pr)), "% came back")
print("  had a change accepted:", len(accepted), "->", pct((accepted["active_days"] > 1).sum(), len(accepted)), "% came back")

contrib.sort_values("total", ascending=False, kind="stable").to_csv(os.path.join(out_folder, "contributors.csv"))

# put printing back to normal and tell the user where everything is
summary_file.close()
sys.stdout = sys.__stdout__
print("done, numbers are in", os.path.join(out_folder, "summary.txt"))