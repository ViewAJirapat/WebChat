# WebChat

**ChatBook**, a small Facebook-like chat web app, was built feature by feature by a **local LLM**
(qwen2.5-coder 14B through Aider, on a GTX 1080 Ti). It was built with the agent swarm harness
Glubokaya-Op (a private repo). Claude acted as chief: it planned the
work, staff agents wrote the frame, specs and hidden tests, and the local model wrote all 30
features. Every feature passed hidden acceptance tests it never saw (937 in total).

What the app does:
- register and log in, search people, friend requests;
- DMs and group chats with live updates, "Seen", unread badges;
- profiles;
- a news feed with posts, likes and comments;
- a Discover page (friends online, people you may know).

## What's on `main`

`main` is the whole project in one tree, laid out like the project folder:

| Path | What it is |
|---|---|
| [`chatbook/`](https://github.com/ViewAJirapat/WebChat/tree/main/chatbook) | **The web app**: the stdlib Python JSON API, sqlite and the plain-JS UI. The features the local LLM wrote are in [`chatbook/src/chatbook/features/`](https://github.com/ViewAJirapat/WebChat/tree/main/chatbook/src/chatbook/features) |
| [`harness/`](https://github.com/ViewAJirapat/WebChat/tree/main/harness) | `swarm.toml` and `tasks/cb-01..cb-30`: each task's spec, hidden tests and reference patch |
| [HANDOFF.md](HANDOFF.md) | Start here to continue the work |
| [LOCAL-MODEL-REPORT.md](LOCAL-MODEL-REPORT.md) | How Claude drove the local model: the prompts, the retry loop and real examples of errors and their fixes |
| [PROGRESS.md](PROGRESS.md), [DESIGN.md](DESIGN.md), `notes/` | The step log, the blueprint, the review backlog |
| `tools/publish-main.sh` | Updates `main` from the working branches |

## Run the app

Python 3.12+, no other dependencies. From `chatbook/`:

```
PYTHONPATH=src python -m chatbook --demo    # http://127.0.0.1:8000, seeds demo users
```

On Windows PowerShell, set `$env:PYTHONPATH = "src"` first. The demo users are for local testing
only.

## Branches

`main` is generated, so don't commit to it. Work happens on three branches, one per local repo,
and `tools/publish-main.sh` merges them into `main` with their full history:

| Branch | Local repo | Lands in `main` at |
|---|---|---|
| `project` | `05_ChatBook/` | the root |
| `chatbook` (+ the 30 `agent/*` feature branches) | `05_ChatBook/chatbook/` | `chatbook/` |
| `harness` | `05_ChatBook/harness/` | `harness/` |

They stay separate because the local model works in a checkout of the `chatbook` repo. That
checkout must never contain the hidden tests, and the harness needs the app as a repo of its own.
To develop, clone the three branches as shown in [HANDOFF.md](HANDOFF.md) section 6.0, not `main`.
Never run `git pull origin main` in a local repo: `main` would bring `chatbook/` and `harness/` into it.
