# Scripts for the 2IRR80 capstone report (team 9, `anthropics/claude-code`)

Every measurement in the report was taken at commit `bf2323b3021c9d3db7a31e1e7d61068c3f704497` of
<https://github.com/anthropics/claude-code>. The changes behind the before/after numbers of proposals P4 and P5 are the two
commits of the branch `demo-b-evolution` in <https://github.com/Prowler1/claude-code>:
`117b7df71430a7fe60fad389850d456820677569` (GitHub Actions pinned to SHAs) and
`99672d13d998080dc2ad9e4d6ebdfcf831fcef29` (five plugin READMEs documented).

All scripts that read the repository must be run **from the root of a clone** of `anthropics/claude-code` (they call
`git ls-files`). Copy the `personB/` folder into the clone root, as done for the measurements, or give the full path.
They need git, GNU grep and Python 3.10 or newer, and use only the Python standard library.

## personB

| Script | Used for (report) | Run from the clone root |
|---|---|---|
| `personB/measure/m5_supply_chain.sh` | M5 and the before/after of P4 | `bash personB/measure/m5_supply_chain.sh` |
| `personB/measure/m5_imports.py` | M5, undeclared Python packages (called by the script above) | `python personB/measure/m5_imports.py` |
| `personB/measure/m6_doc_coverage.py` | M6 and the before/after of P5 | `python personB/measure/m6_doc_coverage.py` |
| `personB/evidence/b3_inventory.py` | evidence for the role stereotypes, (c) | `python personB/evidence/b3_inventory.py` |
| `personB/evidence/b3_skim.py` | evidence for the role stereotypes, (c) | `python personB/evidence/b3_skim.py` |
| `personB/prototypes/add_docs.py` | creates the five README entries of P5 (commit `99672d1`) | `python personB/prototypes/add_docs.py` |
| `personB/crosscheck/m5_process_metrics.py` | cross-check of issue handling (bug issues created 2026-04-01 to 2026-06-30) | `python .../m5_process_metrics.py labels` then `run` |
| `personB/crosscheck/m5_validate_closers.py` | cross-check: who closed a stratified sample of bug issues (seed 42) | `python .../m5_validate_closers.py` |

The two cross-check scripts call the GitHub API and need a read-only token in the environment variable `GITHUB_TOKEN`.
**Never commit a token.** Their SHA-256 hashes at the time of the runs were
`3971aa49f9c64f017a4cc426ba6395bc24f716a3de3d4d21047e6ed163e21925` (`m5_process_metrics.py`, run on 2026-10-17) and
`1c39c7ee53a868050a0a70e4c864b21bbe1f2dd14542dbe5f43b8201427de182` (`m5_validate_closers.py`). Their results depend on the day
they are run, because issues keep closing.

## personA

## health/ — project health of anthropics/claude-code

This folder has the scripts, data and results behind Section 3 (Project health) of the 2IRR80 Group 9 report.

Every number in that section is measured at commit [`bf2323b`](https://github.com/anthropics/claude-code/commit/bf2323b3021c9d3db7a31e1e7d61068c3f704497) of `anthropics/claude-code` (13 October 2026). The analysis period is 15 October 2025 up to and including that commit.

## What is in this folder

```
health/
├── main.py               collects the data from the GitHub REST API into data/
├── contributor_an.py     filtering, activity and contributor analysis -> analysis2/summary.txt
├── process_metrics.py    process metrics and the issue sample -> analysis2/process_summary.txt
├── data/                 the raw data, collected on 15 October 2026
│   ├── commits.csv
│   ├── pull_requests.csv
│   ├── issues.csv
│   ├── reviews.csv
│   └── issue_sample.csv
└── analysis2/            the results (made by the two analysis scripts)
    ├── summary.txt
    ├── process_summary.txt
    ├── contributors.csv
    ├── activity_per_month.csv
    ├── activity_per_month.png
    ├── concentration.png
    ├── new_per_month.png
    └── gaps.png
```

## Setup

You need Python 3 and three packages. In a virtual environment:

```
pip install requests pandas matplotlib
```

All three scripts use relative paths, so run them from inside this folder:

```
cd health
```

## How to run

You do **not** need to run `main.py` to reproduce the report. The data it collected is already in `data/`. Just run the two analysis scripts:

```
python contributor_an.py
python process_metrics.py
```

They read `data/` and (re)write everything in `analysis2/`. Running them on the included data gives exactly the numbers in the report, and the output is the same on every run.

### Collecting the data again (optional)

`main.py` needs a GitHub personal access token in the `GITHUB_TOKEN` environment variable. Never put the token in the code :).

```
export GITHUB_TOKEN=your_token_here      # Windows PowerShell: $env:GITHUB_TOKEN="your_token_here"
python main.py
```

Things to know before you do this:

- `main.py` skips every CSV file that already exists, so delete or move the files in `data/` first if you want fresh data. This also means that if it crashes halfway (for example on a network error), you can just run it again and it continues where it stopped.
- It collects the 365 days before the moment you run it, so new data will not match the report exactly. The analysis scripts still cut everything off at `bf2323b`, but data from before 15 October 2025 is not collected anymore.
- Collecting all issues and one request per pull request for the reviews takes a long time because of GitHub's rate limits. The script waits automatically when it hits the limit.

## What each script does

### main.py

Collects five CSV files through the GitHub REST API:

| File | Contents |
|---|---|
| `commits.csv` | all commits on the default branch, with login, account type, author name and email, number of parents and co-authors |
| `pull_requests.csv` | all pull requests created in the period, with author association and when they were closed or merged |
| `issues.csv` | all issues created in the period (pull requests left out), with labels, close reason, comment and reaction counts |
| `reviews.csv` | all submitted reviews on those pull requests |
| `issue_sample.csv` | stratified random sample: 25 issues per month (seed 42), plus who closed each one |

Who closed an issue is only available through one extra request per issue, which is why that is only collected for the sample. Comments were not collected: there were too many to stay within the rate limits.

### contributor_an.py

Writes `analysis2/summary.txt`, `contributors.csv`, `activity_per_month.csv` and the four figures. It covers:

- the cutoff at `bf2323b` (commits from that commit down, everything else by date)
- the filtering checks: bot accounts (`actions-user`, `[bot]` accounts), the shared `claude` and `ghost` accounts, and one person with several accounts (logins with several names or emails)
- human activity per type and per month
- per-contributor metrics, the key contributors (smallest group with 80% of accepted changes, accepted = commits + merged pull requests) and the five categories (key, newcomer, dormant, one-time, occasional)
- the dormant threshold, taken from the 90th percentile of the gaps between active days (103 days)
- newcomers and the newcomer return rate

Ties in the rankings are broken alphabetically, so the results are the same on every run.

### process_metrics.py

Writes `analysis2/process_summary.txt`. It covers:

- pull request acceptance rate, staff against outside contributors
- issue resolution: share closed, close reasons and time to close
- share of closed issues closed by a bot, from the sample, weighted by the number of issues opened per month
- the sample groups and baselines used in the qualitative analysis and the suggested improvements

Pull requests and issues that were merged or closed after `bf2323b` count as still open. Labels (such as `stale`) and comment counts are as on the collection date, because the API does not show their history.

## Where the report numbers come from

| Report section | Source |
|---|---|
| 3.2 Filtering | `summary.txt`, section FILTERING |
| 3.3 Sampling | `process_summary.txt`, section WHO CLOSES ISSUES |
| 3.4 Contributors, Table 3.1, Figures 3.1–3.3 | `summary.txt`, sections CONTRIBUTORS, CATEGORIES, NEWCOMERS AND RETURN RATE |
| 3.5 Activity metrics, Figure 3.4 | `summary.txt`, section ACTIVITY |
| 3.5 Process metrics | `process_summary.txt`, sections PULL REQUESTS, ISSUES, WHO CLOSES ISSUES |
| 3.6 Qualitative analysis, 3.7 Suggested improvements | `process_summary.txt`, section SAMPLE GROUPS FOR THE QUALITATIVE ANALYSIS |

Quotes and links in the qualitative analysis come from the GitHub threads themselves, not from these files.

## Known limitations of the data

- The stored sample has 323 issues instead of 325 (because we intially deleted a few rows because we were getting a csv read error, so the cause were the commits with unknown end characters which broke the csv so we had to remove it): issues #67457 (June 2026) and #99536 (October 2026) are missing. After the cutoff, 316 sampled issues remain.
- `author_association` only marks people whose organisation membership is public, so some staff may be counted as outside contributors.
- 71 merge commits are left out of all per-person counts, like on GitHub's contributors page.
