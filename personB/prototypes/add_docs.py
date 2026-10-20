"""
Inserts the five missing plugin documentation entries into their READMEs.

Run from the ROOT of the claude-code clone:
    python ../recon/add_docs.py

Each entry is inserted just before a named heading. The script is safe to run twice:
it skips a README that already contains the entry, and it stops with a message if the
heading it needs is not found.
"""
import pathlib

EDITS = [
    {
        "file": "plugins/claude-opus-4-5-migration/README.md",
        "before": "## Learn More",
        "marker": "`claude-opus-4-5-migration`",
        "block": (
            "## Included Skill\n"
            "\n"
            "**`claude-opus-4-5-migration`** (skill): Migrates prompts and code from Claude "
            "Sonnet 4.0, Sonnet 4.5 or Opus 4.1 to Opus 4.5. It updates model strings and "
            "adjusts prompts for known behavioral differences in Opus 4.5. Use it when you "
            "want to move a codebase, prompts or API calls to Opus 4.5. It does not migrate "
            "Haiku 4.5.\n"
        ),
    },
    {
        "file": "plugins/hookify/README.md",
        "before": "## Rule Configuration Format",
        "marker": "`conversation-analyzer`",
        "block": (
            "## Agents and Skills\n"
            "\n"
            "**`conversation-analyzer`** (agent): Reads conversation transcripts to find "
            "behaviors worth preventing with hooks, such as repeated mistakes or signs of "
            "user frustration. It runs when `/hookify` is called without arguments, or when "
            "you ask Claude to look back over the conversation and suggest hooks. It uses "
            "the Read and Grep tools.\n"
            "\n"
            "**`writing-rules`** (skill): Guidance on hookify rule syntax and patterns. "
            "Rules are markdown files with YAML front matter, stored as "
            "`.claude/hookify.{rule-name}.local.md`. It is used when you ask to create, "
            "write or configure a hookify rule.\n"
        ),
    },
    {
        "file": "plugins/plugin-dev/README.md",
        "before": "## Installation",
        "marker": "`skill-reviewer`",
        "block": (
            "## Agents\n"
            "\n"
            "**`skill-reviewer`** (agent): Reviews a newly created or modified skill for "
            "quality and best practices, including how well its description triggers. It "
            "runs proactively after a skill is created, or when you ask to review or "
            "improve a skill.\n"
        ),
    },
    {
        "file": "plugins/pr-review-toolkit/README.md",
        "before": "### Proactive Review",
        "marker": "`/review-pr",
        "block": (
            "### The /review-pr Command\n"
            "\n"
            "**`/review-pr [review-aspects]`**: Runs a comprehensive pull-request review "
            "using several specialized agents, each focused on one aspect of code quality. "
            "The optional argument selects which aspects to review.\n"
        ),
    },
]

problems = 0
for e in EDITS:
    path = pathlib.Path(e["file"])
    if not path.exists():
        print(f"MISSING FILE: {path}  (are you in the claude-code folder?)")
        problems += 1
        continue
    text = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    if e["marker"] in text:
        print(f"already documented, skipped: {path}")
        continue
    lines = text.splitlines(keepends=True)
    idx = next((i for i, ln in enumerate(lines) if ln.rstrip("\r\n") == e["before"]), None)
    if idx is None:
        print(f"HEADING NOT FOUND in {path}: {e['before']!r}  (file left unchanged)")
        problems += 1
        continue
    block = e["block"].replace("\n", eol) + eol
    lines.insert(idx, block)
    path.write_bytes("".join(lines).encode("utf-8"))
    print(f"inserted into {path} (before line {idx + 1}: {e['before']})")

print("done with problems" if problems else "done, all four files handled")
