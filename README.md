# WebChat

**ChatBook**, a small Facebook-like chat web app, was built feature by feature by a **local LLM**
(qwen2.5-coder 14B through Aider, on a GTX 1080 Ti). It was built with the agent swarm harness
[Glubokaya-Op](https://github.com/ViewAJirapat/Glubokaya-Op). Claude acted as chief: it planned the
work, staff agents wrote the frame, specs and hidden tests, and the local model wrote all 30
features. Every feature passed hidden acceptance tests it never saw (937 in total).

What the app does:
- register and log in, search people, friend requests;
- DMs and group chats with live updates, "Seen", unread badges;
- profiles;
- a news feed with posts, likes and comments;
- a Discover page (friends online, people you may know).

## Branches

This repo holds three separate histories, one per folder of the project:

| Branch | Folder | What it is |
|---|---|---|
| `main` | `05_ChatBook/` | This README, [HANDOFF.md](HANDOFF.md) (start here), [PROGRESS.md](PROGRESS.md), [DESIGN.md](DESIGN.md), `notes/` |
| [`chatbook`](https://github.com/ViewAJirapat/WebChat/tree/chatbook) | `05_ChatBook/chatbook/` | The app: the stdlib Python JSON API, sqlite and the plain-JS UI. Feature code is in `src/chatbook/features/` |
| `agent/*` | (branches of `chatbook`) | The 30 accepted feature branches written by the local LLM. Integrates need them as the regression list |
| [`harness`](https://github.com/ViewAJirapat/WebChat/tree/harness) | `05_ChatBook/harness/` | `swarm.toml` and `tasks/cb-01..cb-30` (specs, hidden tests, reference patches) |

The hidden tests are kept out of the app's history on purpose: the local model works in a checkout
of `chatbook` and must never see them.

## Get it

```
git clone --single-branch https://github.com/ViewAJirapat/WebChat.git 05_ChatBook
cd 05_ChatBook
git clone --single-branch -b chatbook https://github.com/ViewAJirapat/WebChat.git chatbook
git clone --single-branch -b harness https://github.com/ViewAJirapat/WebChat.git harness
```

[HANDOFF.md](HANDOFF.md) section 6.0 has the full setup, including the agent branches, the oracle
clone, the harness and Ollama.

## Run the app

Python 3.12+. From `chatbook/`:

```
PYTHONPATH=src python -m chatbook --demo    # http://127.0.0.1:8000, seeds demo users
```

On Windows PowerShell, set `$env:PYTHONPATH = "src"` first. The demo users are for local testing
only.
