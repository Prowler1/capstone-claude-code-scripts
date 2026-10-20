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

## personA and health

To be added by the other authors.
