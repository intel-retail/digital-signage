#!/usr/bin/env bash
# extract_commits.sh
# Usage: bash extract_commits.sh <repo_path> <base_branch> <target_branch>
#
# Outputs one line per non-merge commit between base_branch and target_branch:
#   <short_hash> <subject>
#
# Exit codes:
#   0 - success (may output zero lines if no commits differ)
#   1 - missing arguments
#   2 - repo path not a git repository
#   3 - one or both branch names not found

set -euo pipefail

REPO_PATH="${1:-}"
BASE_BRANCH="${2:-}"
TARGET_BRANCH="${3:-}"

if [[ -z "$REPO_PATH" || -z "$BASE_BRANCH" || -z "$TARGET_BRANCH" ]]; then
  echo "Usage: $0 <repo_path> <base_branch> <target_branch>" >&2
  exit 1
fi

# Validate git repo
if ! git -C "$REPO_PATH" rev-parse --git-dir > /dev/null 2>&1; then
  echo "ERROR: '$REPO_PATH' is not a git repository." >&2
  exit 2
fi

# Fetch so we have up-to-date remote refs and tags (non-fatal if offline)
git -C "$REPO_PATH" fetch --all --tags --quiet 2>/dev/null || true

# Resolve branches (local or remote)
resolve_ref() {
  local repo="$1"
  local branch="$2"
  # Try as-is, then origin/<branch>
  if git -C "$repo" rev-parse --verify "$branch" > /dev/null 2>&1; then
    echo "$branch"
  elif git -C "$repo" rev-parse --verify "origin/$branch" > /dev/null 2>&1; then
    echo "origin/$branch"
  else
    echo ""
  fi
}

BASE_REF=$(resolve_ref "$REPO_PATH" "$BASE_BRANCH")
TARGET_REF=$(resolve_ref "$REPO_PATH" "$TARGET_BRANCH")

if [[ -z "$BASE_REF" ]]; then
  echo "ERROR: Branch '$BASE_BRANCH' not found. Run 'git branch -a' to list branches." >&2
  exit 3
fi

if [[ -z "$TARGET_REF" ]]; then
  echo "ERROR: Branch '$TARGET_BRANCH' not found. Run 'git branch -a' to list branches." >&2
  exit 3
fi

# Output commits: <short_hash> <subject>
# --no-merges skips merge commits; format keeps it machine-readable
git -C "$REPO_PATH" log \
  --no-merges \
  --pretty=format:"%h %s" \
  "${BASE_REF}..${TARGET_REF}"
