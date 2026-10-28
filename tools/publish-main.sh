#!/usr/bin/env bash
# Refresh GitHub "main": the whole project in one browsable tree, merged from the three working
# branches (push those first):
#   root files <- "project"  (the 05_ChatBook folder's own repo: docs, notes, this script)
#   chatbook/  <- "chatbook" (the app)
#   harness/   <- "harness"  (swarm.toml and the tasks)
#
# It works in a throwaway clone, so the local repos are never touched. It only merges, so main's
# history keeps every commit of all three branches. With nothing new it pushes nothing.
#
#   bash tools/publish-main.sh [repo-url]
set -euo pipefail

url="${1:-https://github.com/ViewAJirapat/WebChat.git}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone -q --single-branch -b main "$url" "$tmp"
cd "$tmp"
git fetch -q origin \
  "+refs/heads/project:refs/remotes/origin/project" \
  "+refs/heads/chatbook:refs/remotes/origin/chatbook" \
  "+refs/heads/harness:refs/remotes/origin/harness"

git merge -q --no-edit -m "Merge branch 'project'" origin/project
for dir in chatbook harness; do
  if git cat-file -e "HEAD:$dir" 2>/dev/null; then
    git merge -q --no-edit -X "subtree=$dir/" -m "Merge branch '$dir' into $dir/" "origin/$dir"
  else
    # First time: graft the branch in as $dir/, keeping its history.
    git merge -q -s ours --no-commit --allow-unrelated-histories "origin/$dir"
    git read-tree --prefix="$dir/" -u "origin/$dir"
    git commit -q -m "Add branch '$dir' as $dir/"
  fi
done

git push origin main
