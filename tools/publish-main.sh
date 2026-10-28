#!/usr/bin/env bash
# Update GitHub "main": the whole project in one browsable tree, made from the three working
# branches (push those first):
#   root files <- "project"  (the 05_ChatBook folder's own repo: docs, notes, this script)
#   chatbook/  <- "chatbook" (the app)
#   harness/   <- "harness"  (swarm.toml and the tasks)
#
# main's tree is built straight from the three branch tips, so it always matches them exactly,
# even after a branch was rewritten or someone committed to main. Each new tip becomes a merge
# parent, so main's history keeps every commit of all three branches. It works in a throwaway
# clone, never touches the local repos and never force-pushes. With nothing new it pushes nothing.
#
# Run it from Git Bash. In PowerShell, plain "bash" starts WSL; use Git's bash instead:
#   & "C:\Program Files\Git\bin\bash.exe" E:/Playground_Projects/05_ChatBook/tools/publish-main.sh
#
#   bash tools/publish-main.sh [repo-url]
set -euo pipefail

if [ "$#" -gt 1 ]; then echo "usage: publish-main.sh [repo-url]" >&2; exit 2; fi
url="${1-https://github.com/ViewAJirapat/WebChat.git}"
if [ -z "$url" ]; then echo "publish-main: the repo url is empty" >&2; exit 2; fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone -q --no-checkout --single-branch -b main "$url" "$tmp/repo"
cd "$tmp/repo"
git fetch -q origin \
  "+refs/heads/project:refs/remotes/origin/project" \
  "+refs/heads/chatbook:refs/remotes/origin/chatbook" \
  "+refs/heads/harness:refs/remotes/origin/harness"

export GIT_INDEX_FILE="$tmp/publish.index"
git read-tree origin/project
git read-tree --prefix=chatbook/ origin/chatbook
git read-tree --prefix=harness/ origin/harness
tree="$(git write-tree)"

parents=(-p main)
for branch in project chatbook harness; do
  git merge-base --is-ancestor "origin/$branch" main || parents+=(-p "origin/$branch")
done
if [ "$tree" = "$(git rev-parse 'main^{tree}')" ] && [ "${#parents[@]}" -eq 2 ]; then
  echo "main is already current"
  exit 0
fi

short() { git rev-parse --short "origin/$1"; }
commit="$(git commit-tree "$tree" "${parents[@]}" \
  -m "Update main: project $(short project), chatbook $(short chatbook), harness $(short harness)")"
git push origin "$commit:refs/heads/main"
