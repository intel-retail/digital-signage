---
name: generate-changelog
description: >
  Generates or updates a CHANGELOG.md file for the current repository by
  analyzing git commit history between two branches or tags. Use this skill whenever the
  user asks to create, update, or generate a changelog, release notes from git
  history, or compare two branches or tags (e.g., "generate changelog for release-2026.1.0
  vs main", "update CHANGELOG.md", "what changed between branches or tags"). The skill
  produces entries categorized into Added, Changed, Removed, Fixed, Security, and
  Documentation sections, matching the repository's established changelog format.
---

# Changelog Generator

Generates or updates `CHANGELOG.md` by extracting and categorizing commits between
two git branches or tags. Follows the [Keep a Changelog](https://keepachangelog.com/) style
used by the current repository.

## Inputs

Collect from the user (or infer from context):

| Parameter | Description | Example |
|-----------|-------------|---------|
| `target_branch` | Branch with new changes | `release-2026.1.0` |
| `base_branch` | Branch to compare against | `main` |
| `version_label` | Version string for the entry | `2026.1.0` |
| `release_date` | Release month and year | `June 2026` |
| `repo_path` | Absolute path to git repo | auto-detected from workspace |
| `output_file` | Path to write CHANGELOG.md | `CHANGELOG.md` in repo root |
| `repo_url` | GitHub URL for PR/commit links | inferred from `git remote` |

**Before proceeding:** If the user has not explicitly mentioned a release version, ask them:
> "What release version should be used for this changelog entry? (e.g., 2026.1.0, v1.1.0)"

If `repo_path` is not given, resolve it by running `git rev-parse --show-toplevel`
from the current working directory or use the workspace root.

If `repo_url` is not given, run:
```bash
git -C <repo_path> remote get-url origin
```
and strip `.git` suffix. Typical format: `https://github.com/intel-retail/digital-signage`

## Workflow

### Step 1 – Extract commits

Run the extraction script to get the commit list between the two branches or tags:

```bash
bash .github/skills/generate-changelog/scripts/extract_commits.sh \
  <repo_path> \
  <base_branch> \
  <target_branch>
```

The script outputs one commit per line in the format:
```
<short_hash> <subject>
```

If the script is unavailable, run this git command directly:
```bash
git -C <repo_path> log --no-merges \
  --pretty=format:"%h %s" \
  <base_branch>..<target_branch>
```

Also collect PR numbers referenced in commit messages (pattern `(#\d+)` or `#\d+`).

### Step 2 – Categorize commits

Classify each commit into a section based on keywords in the subject line.
Apply the **first matching rule**:

| Section | Keywords / patterns (case-insensitive) |
|---------|----------------------------------------|
| **Security** | `security`, `cve`, `vulnerability`, `bump`, `trivy`, `patch`, `upgrade` (dependency) |
| **Fixed** | `fix`, `fixed`, `repair`, `resolve`, `hotfix`, `revert` |
| **Added** | `add`, `added`, `new`, `introduce`, `enable`, `support`, `feature`, `implement` |
| **Removed** | `remove`, `removed`, `delete`, `deleted`, `drop`, `deprecat` |
| **Documentation** | `doc`, `docs`, `documentation`, `readme`, `changelog`, `typo`, `spelling` |
| **Changed** | everything else |

> Tip: If a commit message is ambiguous, prefer the section that better serves the
> reader. Merge commits and automated bot commits (e.g., Dependabot) should be
> placed in **Security** or **Changed** as appropriate.

### Step 3 – Format the entry

Read `references/changelog-format.md` for the exact structure and examples.

Key rules:
- Write each bullet in past tense, sentence case.
- Append the PR or commit reference at the end of each line: `([#NN])` for PRs,
  `([abcdef])` for bare commits.
- Omit sections that have no entries.
- At the bottom of the new version block, add a reference link for every PR/commit
  cited, pointing to the GitHub URL:
  - PR: `[#NN]: <repo_url>/pull/NN`
  - Commit: `[abcdef]: <repo_url>/commit/<full_hash>`

### Step 4 – Write or update CHANGELOG.md

**Creating a new file:** Write the complete file (header + new version block).

**Updating an existing file:** Insert the new version block immediately after the
`# Changelog` header line and the introductory paragraph, *before* any existing
`## [...]` sections. Preserve all existing content exactly.

Use the output file path resolved in the Inputs step. Confirm with the user before
overwriting if the file already exists and contains content for the same version.

### Step 5 – Confirm output

After writing the file, print a short summary:
- How many commits were processed
- Count per section
- Path of the written file

Example:
```
Changelog updated: CHANGELOG.md
Version: 2026.1.0 (June 2026)
Commits processed: 24
  Added: 4 | Changed: 8 | Fixed: 6 | Security: 3 | Documentation: 3
```

## Edge cases

- **No commits found:** If `git log` returns nothing, inform the user. Possible
  causes: branches are identical, wrong branch names, or shallow clone. Suggest
  running `git fetch --all` first.
- **Duplicate version:** If CHANGELOG.md already contains `## [<version>]`, ask
  the user whether to replace it or append to it.
- **Detached HEAD / missing branch:** Validate that both branches exist before
  running the log command. Use `git branch -a` to list available branches.
- **No GitHub PR number:** Some commits won't have a `#NN` reference. Use the
  short commit hash as the reference instead.
