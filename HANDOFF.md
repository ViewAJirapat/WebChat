# Handoff: ChatBook (2026-10-28, all 30 features done, on GitHub as WebChat)

This is for whoever continues the project, human or AI, starting with no prior context. Read this file
first, then `PROGRESS.md` (the step log), then `DESIGN.md` (the blueprint and source of truth).
**On a new PC, start with section 6.0.**

---

## 1. Objective & Status

**Goal:** a Facebook-like chat web app built by a **local LLM** (qwen2.5-coder 14B via Aider,
architect mode, on a GTX 1080 Ti) through the swarm harness in `E:\Playground_Projects\04_AgentSwarm`.
A chief (the AI that coordinates):
- plans the work;
- has staff agents write the frame, specs and hidden tests;
- issues `swarm` commands;
- reviews the results.

Feature code comes **only** from the local LLM, through the harness.

The product is a stdlib-only Python WSGI JSON API with sqlite and a plain-JS single-page UI. It has
30 auto-discovered feature folders (the shopapi pattern) built on a protected frame that staff wrote.

| Step | State |
|---|---|
| 1. Design: judge panel, `DESIGN.md` | Done |
| 2. Frame, harness config, frame review, tasks cb-01..cb-22 | Done. The frame is frozen, except for the CONTRACT gate added in Wave 1 |
| 3. Validate on the oracle + reference integrate | Done: 22/22 |
| 4. Development waves 1-3 (local LLM) | **Done.** 22/22 tasks were written by qwen 14B and accepted. Wave 1 took 26 min, Wave 2 66 min, Wave 3 35 min |
| 5. Integrate + browser smoke | Done. The MVP reached `main` @ `4ff5b4e`: 645 hidden tests green |
| 6. Stretch cb-23..cb-30 (Waves 4-5, local LLM) | **Done. All 30 features are on `chatbook` `main` @ `87de89e`.** Wave 4 took 42 min (5/5), Wave 5 27 min (3/3). All gates and 937 hidden tests are green, and the final browser smoke passed. Provenance: all `local-14b-arch`, 0 `oracle` |
| 7. Next | **Owner's choice:** a polish wave from `notes/polish-backlog.md` (14 items; item 10 is medium, about privacy), or new features |

**State at handoff (verified):**
- `chatbook`: `main` @ `87de89e`, clean, one worktree, no stubs left.
  - 30 accepted `agent/*--local-14b-arch--*` branches. Keep them: they are the regression list for later integrates.
  - 6 old `integration/2026*` branches. They can be deleted.
- `chatbook-oracle`: `main` @ `87de89e`, clean, only `main`. It is current.
- `harness`: `main` @ `2ecb8e5`, clean, with tasks cb-01..cb-30.
- **GitHub:** everything is pushed to https://github.com/ViewAJirapat/WebChat. Each local repo's
  `main` pushes to its own working branch:

  | Remote branch | Local repo | Contents |
  |---|---|---|
  | `project` | `05_ChatBook/` | README, this file, PROGRESS, DESIGN, `notes/`, `tools/publish-main.sh` |
  | `chatbook` + the 30 `agent/*` | `chatbook/` | the app |
  | `harness` | `harness/` | `swarm.toml` and the tasks |
  | `main` (default) | none | **Generated.** The whole project in one tree: `project` at the root, `chatbook` in `chatbook/`, `harness` in `harness/`, merged with full history by `tools/publish-main.sh`. It is for browsing and download; never commit to it or work in a clone of it |

  The old `integration/*` branches and `harness/runs/` (the logs, which are git-ignored) were not
  pushed. `chatbook-oracle/` is a local clone and is never pushed.
- Ollama was started from the chief's session and stops when that session ends. Restart it as shown in 6.1.
- **Don't validate old tasks on the oracle:** `main` already contains their features, so their baseline check fails by design. Validate only new tasks (or re-opened ones whose stub was reset).

**What the product does** (browser-checked):
- **MVP:** register and login, people search, friend requests (accept or decline), friends list, DMs
  and group chats with Messenger-style bubbles, live updates every ~3 s, "Seen", unread badges and an
  "(n)" title count, creating and renaming groups, viewing and editing profiles.
- **Stretch:** a news feed of your own and your friends' posts, with like/unlike, comments (add,
  delete) and deleting your own posts; a post page; and a Discover page with friends online in the
  last 60 s ("Message" opens the DM) and "People you may know" with mutual-friend counts and
  "Add friend".

Try it (it serves on http://127.0.0.1:8000; the `PORT`, `HOST` and `CHATBOOK_DB` env vars change that):
```
cd E:\Playground_Projects\05_ChatBook\chatbook
E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/python.exe -m chatbook --demo
```
`--demo` seeds demo users into an empty database and prints their logins.

---

## 2. Decisions & Dead-Ends

### 2a. Decisions and why
- **The harness repo `04_AgentSwarm` is never modified** (owner's rule). Drive it from outside:
  `E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/swarm.exe -c E:/Playground_Projects/05_ChatBook/harness/swarm.toml -t <target> <cmd>`
  (or `uv run --project E:/Playground_Projects/04_AgentSwarm swarm ...`).
- **The frame owns everything that crosses features:**
  - users, sessions and auth;
  - the whole sqlite schema;
  - the social and chat helpers;
  - validators and the clock;
  - UI page discovery;
  - the test `Client` and the `run_page` headless runner.

  Features can't import each other (archlint).
- **Every stub starts with a CONTRACT block**, because in architect mode the editor pass never sees
  the task prompt. Since Wave 1, a **CONTRACT gate** in `tools/check_extra.py` requires each block
  to be unchanged (snapshot in `tools/contracts.json`). The first autofix step,
  `--restore-contracts`, puts a block back if it was deleted entirely. This was added after cb-05
  deleted its block.
- **Validation runs only on target `chatbook-oracle`.** `integrate` keeps the newest run per task
  by name, so `oracle` would beat `local-14b-arch`.
  - **Never run `validate` or `-e oracle` on target `chatbook`.**
  - Integrate `chatbook` only with explicit lists of worker branches.
- **Each wave's integrate includes every earlier accepted branch.** This re-runs all earlier hidden suites as regression.
- **Review findings that the spec requires are spec debt, not worker errors.** They go to
  `notes/polish-backlog.md`. They are fixed by changing the spec or frame and then re-running the
  page through the local LLM, never by hand-editing feature code.
- **Engine:** `local-14b-arch`.
  - Fallbacks: `local-14b` (single pass) and `local-7b-arch` (16k ctx). Neither was needed.
  - deepseek-16b is excluded because it ignores instructions.
  - The `claude` CLI is signed out.

### 2b. Dead-ends: do not repeat
1. **Many agents in parallel** burn through the session limit fast. Run batches of about 5, and checkpoint `PROGRESS.md` before long runs.
2. **Restarting interrupted writers from scratch** wastes work. Tell re-runs to "check and complete the files on disk".
3. **Staff committing in parallel** in the harness repo collide on the git index.
4. **Judging work on `chatbook` with oracle branches present** (see 2a).
5. **Running a wave while Ollama is on the CPU.** Wave 1 attempt 1 timed out on every task. Cause:
   Ollama 0.40.11's `cuda_v13` dropped Pascal (cc 6.1). **Always start with `OLLAMA_LLM_LIBRARY=cuda_v12`, and check GPU offload before a wave.**
6. **`ollama app.exe`** (the tray UI) fails from a non-interactive shell. Use `ollama.exe serve`.
7. **`ollama run` / `ollama list` / `ollama ps` from the agent shell hang.** Use the HTTP API
   instead: `/api/generate` (non-streaming), `/api/tags`, `/api/ps`.
8. **Sandbox loopback:** in the agent sandbox, anything that touches `127.0.0.1` fails with `WinError 10013`. That includes Ollama, `swarm run`, and `validate`/`integrate` (because `tests/test_app.py` opens a local socket). Run those commands outside the sandbox.

---

## 3. Constraints
- **Hardware:** GTX 1080 Ti 11 GB, 16 GB RAM. qwen 14B at 8k context runs at 88% GPU, ~17 tok/s.
- **Workers:**
  - 8k context;
  - whole-file replies capped at 4096 tokens;
  - files of about 120 lines or fewer;
  - prompts of about 700 words or fewer;
  - ASCII only in asserted strings.
- **Measured token use:** architect input 3.9-5.7k (target < 5.5k); editor input + output ≤ 4.8k (target < 7k).
- **Platform:** Windows, PowerShell 5.1, `core.autocrlf=true`. The repos use `.gitattributes` `* text=auto eol=lf`.
- **Owner's rules:**
  - Ask before downloading models.
  - Push to GitHub only when the owner asks (routine in 6.0). Never use `swarm run --push`: it
    would push every worker branch, including rejected ones. Never commit to GitHub `main`
    directly: `tools/publish-main.sh` generates it.
  - Leave `D:\Thesis_workspace` and `04_AgentSwarm` alone.
- **Never edit** frame tests, task `acceptance/` folders or a `solution.patch` to make a worker pass.
  Never hand-write feature code into `chatbook`.

---

## 4. Key Artifacts (all under `E:\Playground_Projects\05_ChatBook`)
- `README.md`: the GitHub front page, which explains the branch layout.
- `tools/publish-main.sh`: rebuilds GitHub `main` from the three working branches.
- `DESIGN.md`:
  - §3 the frame API;
  - §4 `swarm.toml`;
  - §6.1 the staff task checklist;
  - §6.5 the task specs, including the stretch cb-23..cb-30;
  - §7 procedures (7.2 waves, 7.3 smoke);
  - §8 the failure ladder.
- `PROGRESS.md`: the step log.
- `notes/polish-backlog.md`: spec, frame and tooling gaps found by the reviews.
- `notes/frame-writer-reports.md`: the frame writers' choices.
- `chatbook/`: the product repo.
  - Feature code is in `src/chatbook/features/<name>/handler.py` or `ui.js`.
  - The frame is in `src/chatbook/core/`, `testing.py` and `tools/`.
- `chatbook-oracle/`: a throwaway validation clone.
- `harness/`:
  - `swarm.toml`;
  - `tasks/cb-01..cb-30/`, each with `task.toml`, `acceptance/test_cbNN_<name>.py` and `solution.patch`;
  - `runs/`, which is git-ignored and holds the per-attempt logs, `wave*.log` and `cb05-rerun.log`.

**Health check.** Run these from `chatbook`, where `py` = `E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/python.exe`:
- `py -m ruff check .`
- `py -m ruff format --check .`
- `py -m mypy src`
- `py -m pytest -q -p no:cacheprovider tests` (290 passed)
- `py tools/check_extra.py`
- `swarm -t chatbook archlint`

---

## 5. Open Issues
1. **Polish backlog:** 14 items, see `notes/polish-backlog.md`. All of them are spec or frame debt:
   the worker followed its CONTRACT every time. No security hole was found; the pages escape all
   HTML. The biggest are:
   - **(10, medium, privacy)** after an unfriend, a user can't delete their own comment or like on the ex-friend's post. This needs a product decision first;
   - (1, 2, 9) "Show older" / "Show more" re-mount the page, which loses the draft, and fail past the API's limit cap;
   - (12) one-click Delete with no confirm.
2. **Frame tooling notes:**
   - restore skips a file that keeps only the stub's first line;
   - a check_extra comment gives the wrong reason for `backslashreplace`;
   - retry prompts can reach about 5.7k architect tokens.
3. **Aider exit hang:** cb-09's Aider applied its edit and then didn't exit until the 900 s timeout.
   This happened once in 23 runs, and the harness still accepted the edit. Watch for repeats.
4. **Hidden-test lesson from the stretch authoring:** parametrize long string values with explicit
   `ids=[...]`. Otherwise 2000-char pytest ids flood the worker's 3000-char feedback, and it never
   sees the assertion.

---

## 6. Immediate Next Steps

### 6.0 Set up on another PC, and push updates

**Prerequisites:**
- Git;
- Python 3.12+ and [uv](https://docs.astral.sh/uv/);
- Node.js 24 (the UI runner `tools/uirun.js` and the JS gate need `node` on PATH);
- Ollama.

**Keep the same paths if you can.** `harness/swarm.toml` names
`E:/Playground_Projects/04_AgentSwarm/config/aider.model.settings.yml` in each engine block, and
the commands in this file use `E:/Playground_Projects/...`. If the paths differ, edit the
`model_settings` lines. The repo paths in `swarm.toml` are relative (`../chatbook`).

1. **Get the harness.** It is a separate private repo, and it is never modified for ChatBook. Clone
   it into the folder name used here, then follow its own HANDOVER.md section 6 (`uv sync`; the
   models are about 9 GB for qwen 14B):
   ```
   cd E:\Playground_Projects
   git clone https://github.com/ViewAJirapat/Glubokaya-Op.git 04_AgentSwarm
   ```
2. **Get ChatBook.** Clone it as three repos from the three working branches, not from `main`
   (`main`'s `chatbook/` folder is not a repo the harness can use). `--single-branch` keeps each
   clone to its own history:
   ```
   git clone --single-branch -b project https://github.com/ViewAJirapat/WebChat.git 05_ChatBook
   cd 05_ChatBook
   git clone --single-branch -b chatbook https://github.com/ViewAJirapat/WebChat.git chatbook
   git clone --single-branch -b harness https://github.com/ViewAJirapat/WebChat.git harness
   ```
3. **Make the clones work like the originals.** The harness's base branch is `main`, and an
   integrate needs the 30 accepted `agent/*` branches as local branches. In `chatbook`:
   ```
   git -C chatbook branch -m chatbook main
   git -C chatbook config remote.origin.push refs/heads/main:refs/heads/chatbook
   git -C chatbook config --add remote.origin.fetch "+refs/heads/agent/*:refs/remotes/origin/agent/*"
   git -C chatbook fetch origin "refs/heads/agent/*:refs/heads/agent/*"
   ```
   In `harness`, and in the root folder:
   ```
   git -C harness branch -m harness main
   git -C harness config remote.origin.push refs/heads/main:refs/heads/harness
   git branch -m project main
   git config remote.origin.push refs/heads/main:refs/heads/project
   ```
   Then make the oracle clone. Do this after the rename, so it gets `main`:
   ```
   git clone chatbook chatbook-oracle
   ```
4. **Check it:** run the health check in section 4 (290 frame tests), then
   `swarm -t chatbook archlint`.
5. **On a non-Pascal GPU** (e.g. an RTX 40xx), Ollama's default CUDA library works. The
   `OLLAMA_LLM_LIBRARY=cuda_v12` in 6.1 is only for the 1080 Ti. The token limits in section 3
   were measured on the 1080 Ti with 8k context; keep them unless you re-measure.

**Push updates** (only when the owner asks). Each repo pushes to its own branch; then refresh
`main`:
```
git -C E:/Playground_Projects/05_ChatBook push                      # docs  -> project
git -C E:/Playground_Projects/05_ChatBook/chatbook push             # app   -> chatbook
git -C E:/Playground_Projects/05_ChatBook/harness push              # tasks -> harness
git -C E:/Playground_Projects/05_ChatBook/chatbook push origin <newly accepted agent/... branch>
bash E:/Playground_Projects/05_ChatBook/tools/publish-main.sh      # merge all three into main
```
On the original PC these remotes and push settings are already in place. Push new `agent/*`
branches by name and only accepted ones; rejected attempts stay local. The publish script works in
a throwaway clone, so it never touches the local repos. It only merges, and it pushes nothing when
`main` is already current.

### 6.1 Start Ollama on the GPU (outside the sandbox)
```powershell
$env:OLLAMA_MODELS = "E:\Playground_Projects\04_AgentSwarm\models"
$env:OLLAMA_LLM_LIBRARY = "cuda_v12"
$env:OLLAMA_VULKAN = "false"
& "C:\Users\viewj\AppData\Local\Programs\Ollama\ollama.exe" serve     # keep it running
```
Then warm it up and check it, from a second shell:
```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -ContentType application/json `
  -Body '{"model":"qwen2.5-coder:14b","prompt":"Reply with OK","stream":false}'
Invoke-RestMethod http://127.0.0.1:11434/api/ps    # size_vram should be ~9.5 GB, not 0
```

### 6.2 Pick the next phase (ask the owner)
The stretch features (option (b) below) are **done**. What's left is (a), or new features designed the same way.

**(a) Polish wave.** Take the items in `notes/polish-backlog.md`. For each one:
1. Staff change the frame, or the stub CONTRACT and the DESIGN §6.5 spec.
2. Run `py tools/check_extra.py --write-contracts`.
3. Write a follow-up task (e.g. `cb-18b-page_chat`). Reuse the old acceptance tests and add the new ones.
4. Validate it on the oracle.
5. Run it on `chatbook`.
6. Integrate it with all 30 accepted branches. The re-implemented page's new branch replaces its old one.

A re-opened task needs its stub put back on the base, since `main` has the old implementation. Make
the follow-up task's base a staff commit that resets that one file to its (new) CONTRACT stub.

**(b) DONE. Stretch features cb-23..cb-30, in Waves 4-5:** posts, likes, comments, presence,
suggestions, page_feed, page_post and page_discover.
1. Staff author the tasks, in batches of about 5, following DESIGN §6.1.
2. `git -C chatbook-oracle pull --ff-only`, then `swarm -t chatbook-oracle validate <new tasks> -j 2`.
3. Run them on `chatbook` with `-j 1`.
4. Integrate the new branches together with all 22 accepted branches.
5. Check provenance.
6. Fast-forward `main`.
7. Run the smoke test.

### 6.3 Per-wave routine (as used in Waves 1-3)
1. Check that the oracle is current and that the tasks validate.
2. Start the wave:
   ```
   swarm -t chatbook run <tasks> -j 1
   ```
   Put the log in `harness/runs/<wave>.log`.
3. Triage failures with DESIGN 8.1.
4. Integrate this wave's passing branches together with all earlier accepted ones:
   ```
   swarm -t chatbook integrate <this wave's passing> <all earlier accepted>
   ```
5. Check provenance with `git -C chatbook log --format=%b main..integration/<stamp>`. Every commit must be `local-*`, and no file may be outside `features/`.
6. Have the code reviewed by a multi-lens review with skeptic verification.
7. Run the browser smoke test.
8. `git -C chatbook merge --ff-only integration/<stamp>`, then `swarm -t chatbook clean`. Don't pass `--branches`: the accepted branches must stay.
9. Update `PROGRESS.md`.
