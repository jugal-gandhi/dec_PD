#!/usr/bin/env bash
# Force-push results/<name> as a single orphan commit to branch <branch>.
# Usage: publish_results.sh <name> <branch>    (needs GITHUB_TOKEN)
set -euo pipefail
NAME=$1
BRANCH=$2
SRC="results/$NAME"
[ -d "$SRC" ] || { echo "nothing to publish"; exit 0; }

TMP=$(mktemp -d)
cp -r "$SRC"/. "$TMP"/
cd "$TMP"
git init -q
git checkout -q -b "$BRANCH"
git add -A
git -c user.name="layout-ci" -c user.email="actions@users.noreply.github.com" \
    commit -q -m "Results for ${GITHUB_SHA} (run ${GITHUB_RUN_ID})"
git push -q -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "HEAD:refs/heads/$BRANCH"
echo "Published $SRC to $BRANCH"
