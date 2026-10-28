# Handoff: ChatBook (2026-10-28, all 34 tasks done incl. polish P1, P2 next, on GitHub as WebChat)

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
32 auto-discovered feature folders (the shopapi pattern) built on a protected frame that staff wrote.

| Step | State |
|---|---|
| 1. Design: judge panel, `DESIGN.md` | Done |
| 2. Frame, harness config, frame review, tasks cb-01..cb-22 | Done. The frame is frozen, except for the CONTRACT gate added in Wave 1 |
| 3. Validate on the oracle + reference integrate | Done: 22/22 |
| 4. Development waves 1-3 (local LLM) | **Done.** 22/22 tasks were written by qwen 14B and accepted. Wave 1 took 26 min, Wave 2 66 min, Wave 3 35 min |
| 5. Integrate + browser smoke | Done. The MVP reached `chatbook` `main` @ `4ff5b4e`: 645 hidden tests green |
| 6. Stretch cb-23..cb-30 (Waves 4-5, local LLM) | **Done. All 30 features are on `chatbook` `main` @ `87de89e`.** Wave 4 took 42 min (5/5), Wave 5 27 min (3/3). All gates and 937 hidden tests are green, and the final browser smoke passed. Provenance: all `local-14b-arch`, 0 `oracle` |
| 7. Polish P1 (backlog 10(a) + 11, cb-31..cb-34, local LLM) | **Done (2026-10-28).** The owner chose the polish wave in 3 small waves: P1 backend items 10+11 (item 10 = (a) + a new "My activity" page), P2 frame helpers + pages, P3 paging. P1: 4/4 tasks passed on the first try in 18.5 min. Integrate of 32 branches: all gates and 1009 hidden tests green; review 0 findings; browser smoke passed. **`chatbook` `main` @ `b21aa4b`** |
| 8. Next | **Design P2** (frame helpers + pages: items 12, 8, 6/13, 4, 7), then P3 paging (1, 2, 9, 14). See 6.4 |

**State at handoff (verified):**
- `chatbook`: `main` @ `b21aa4b`, fast-forwarded from `integration/20261028-221919` (the P1
  merge; before it `1fbb04a`, the P1 frame commit). Clean, one worktree. **Not pushed:** `main`
  is 9 ahead of `origin/chatbook` (the frame commit, 4 worker commits, 4 merges). All gates are
  green, with 291 frame tests.
  - 34 accepted `agent/*--local-14b-arch--*` branches. Keep them all. The regression list is
    `harness/accepted.txt`: 32 active, plus 2 retired (cb-24-likes and cb-25-comments, superseded
    by cb-31 and cb-32). Retired branches stay as records.
  - 7 `integration/2026*` branches (the newest is the P1 merge). They can be deleted.
- `chatbook-oracle`: `main` @ `b21aa4b`, clean, only `main`. It is current.
- `harness`: `main` @ `80cc90e`, clean, with tasks cb-01..cb-34 and `accepted.txt`. **Not
  pushed:** 2 ahead of `origin/harness` (`13c35a4` the P1 tasks + `accepted.txt`, `80cc90e` the
  P1 branches added and cb-24/cb-25 retired).
- This folder: the P1 docs commits are local, not pushed.
- **GitHub:** everything up to the end of the stretch is pushed to
  https://github.com/ViewAJirapat/WebChat. The P1 commits and the 4 P1 branches are not pushed
  yet (push only when the owner asks, 6.0). Each local repo's `main` pushes to its own working
  branch:

  | Remote branch | Local repo | Contents |
  |---|---|---|
  | `project` | `05_ChatBook/` | README, this file, PROGRESS, DESIGN, `notes/`, `tools/publish-main.sh` |
  | `chatbook` + the accepted `agent/*` (30 so far) | `chatbook/` | the app |
  | `harness` | `harness/` | `swarm.toml` and the tasks |
  | `main` (default) | none | **Generated.** The whole project in one tree: `project` at the root, `chatbook` in `chatbook/`, `harness` in `harness/`, merged with full history by `tools/publish-main.sh`. It is for browsing and download; never commit to it, work in a clone of it or pull it into a local repo (see the warning in 6.0) |

  The old `integration/*` branches and `harness/runs/` (the logs, which are git-ignored) were not
  pushed. `chatbook-oracle/` is a local clone and is never pushed.
- Ollama was started from the chief's session and stops when that session ends. Restart it as shown in 6.1.
- **Don't validate old tasks on the oracle:** the oracle's `main` already contains their features, so their baseline check fails by design. Validate only new or reopened tasks, and never again after they are accepted. All of cb-01..cb-34 are accepted now, so none of them is validated again.

**What the product does** (browser-checked):
- **MVP:** register and login, people search, friend requests (accept or decline), friends list, DMs
  and group chats with Messenger-style bubbles, live updates every ~3 s, "Seen", unread badges and an
  "(n)" title count, creating and renaming groups, viewing and editing profiles.
- **Stretch:** a news feed of your own and your friends' posts, with like/unlike, comments (add,
  delete) and deleting your own posts; a post page; and a Discover page with friends online in the
  last 60 s ("Message" opens the DM) and "People you may know" with mutual-friend counts and
  "Add friend".
- **Polish P1:** after an unfriend, you can still remove your own like and delete your own
  comment on the ex-friend's post. "My activity" (nav "Activity") lists them with Unlike and
  Delete buttons. A hidden and a missing comment give the same 404.

Try it in PowerShell (it serves on http://127.0.0.1:8000; the `PORT`, `HOST` and `CHATBOOK_DB`
env vars change that). The package lives in `src/`, so `PYTHONPATH` must point there:
```powershell
cd E:\Playground_Projects\05_ChatBook\chatbook
$env:PYTHONPATH = "src"
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
- **Each wave's integrate includes every branch in `harness/accepted.txt`** (the regression list
  since P1; before it, every earlier accepted branch). This re-runs all earlier hidden suites as
  regression. A wave that reopens a feature leaves out only the old branches whose replacement
  passed (DESIGN 7.2 step 4).
- **A finished feature is reopened in place** (since P1). Staff change only its CONTRACT block on
  `main`, and the model edits its own code below it. A stub reset is the fallback (DESIGN 8.1
  step 4). The reopened task supersedes its old branch: it carries the old suite, with only the
  cases the owner's decision contradicts changed. The old branch moves to the retired block of
  `accepted.txt` only once its replacement is accepted. Old task folders are never edited.
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
- `tools/publish-main.sh`: updates GitHub `main` from the three working branches (see 6.0).
- `DESIGN.md`:
  - §3 the frame API;
  - §4 `swarm.toml`;
  - §6.1 the staff task checklist;
  - §6.5 the task specs, including the stretch cb-23..cb-30 and Polish P1 cb-31..cb-34;
  - §7 procedures (7.2 waves, 7.3 smoke);
  - §8 the failure ladder.
- `PROGRESS.md`: the step log.
- `notes/polish-backlog.md`: spec, frame and tooling gaps found by the reviews.
- `notes/polish-p1-design.md`: the P1 design (decisions, every hidden test, prompts, and the
  runbook in G.4). P1 is done; this file is the model for the P2 design.
- `notes/frame-writer-reports.md`: the frame writers' choices.
- `chatbook/`: the product repo.
  - Feature code is in `src/chatbook/features/<name>/handler.py` or `ui.js`.
  - The frame is in `src/chatbook/core/`, `testing.py` and `tools/`.
- `chatbook-oracle/`: a throwaway validation clone.
- `harness/`:
  - `swarm.toml`;
  - `tasks/cb-01..cb-34/`, each with `task.toml`, `acceptance/test_cbNN_<name>.py` and `solution.patch`;
  - `accepted.txt`: the regression list, one accepted branch per line (32 now), and a
    `# retired:` block for branches whose replacement was accepted (cb-24, cb-25);
  - `runs/`, which is git-ignored and holds the per-attempt logs, `wave*.log`, `cb05-rerun.log`
    and `p1*.log`.

**Health check.** Run these from `chatbook`, where:
- `py` = `E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/python.exe`;
- `swarm` = `E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/swarm.exe -c E:/Playground_Projects/05_ChatBook/harness/swarm.toml`.
  Without `-c`, swarm loads 04_AgentSwarm's own config, which has no `chatbook` target.
- `py -m ruff check .`
- `py -m ruff format --check .`
- `py -m mypy src`
- `py -m pytest -q -p no:cacheprovider tests` (291 passed since the P1 frame commit; 290 before)
- `py tools/check_extra.py`
- `swarm -t chatbook archlint`

---

## 5. Open Issues
1. **Polish backlog:** 14 items, see `notes/polish-backlog.md`. All of them are spec or frame debt:
   the worker followed its CONTRACT every time. No security hole was found; the pages escape all
   HTML. **Items 10 (medium, privacy) and 11 are done in P1** (cb-31..cb-34, `chatbook`
   `b21aa4b`). Of the 12 left, the biggest are:
   - (1, 2, 9) "Show older" / "Show more" re-mount the page, which loses the draft, and fail past the API's limit cap;
   - (12) one-click Delete with no confirm (now also on the Activity page);
   - (8) buttons stay enabled while busy; a post page left open after an unfriend toasts "post not found" and stays stale (known P1 behaviour).
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
   integrate needs the branches listed in `harness/accepted.txt` as local branches. The fetch of
   `refs/heads/agent/*` below also brings the retired branches. They stay as records (they are
   ancestors of `main`). In `chatbook`:
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
4. **Check it:** run the health check in section 4 (291 frame tests, then archlint).
5. **On a non-Pascal GPU** (e.g. an RTX 40xx), Ollama's default CUDA library works. The
   `OLLAMA_LLM_LIBRARY=cuda_v12` in 6.1 is only for the 1080 Ti. The token limits in section 3
   were measured on the 1080 Ti with 8k context; keep them unless you re-measure.

> **Never pull, merge or check out GitHub `main` in any of the three local repos.** Use plain
> `git pull` and `git push`: they follow `project`, `chatbook` and `harness`. Also don't use the
> GitHub quick-start `git push -u origin main`. `main` contains `chatbook/` and `harness/`, so
> `git pull origin main`:
> - in the root folder overwrites the nested repos' working files, and uncommitted work there is lost;
> - in `chatbook` puts the hidden tests into the app repo, where the worker would see them.
>
> No git setting can block this, so it is a rule. Before pushing `chatbook`, check that
> `git -C chatbook ls-files harness` prints nothing.

**Push updates** (only when the owner asks). Each repo pushes to its own branch; then refresh
`main`:
```
git -C E:/Playground_Projects/05_ChatBook push                      # docs  -> project
git -C E:/Playground_Projects/05_ChatBook/chatbook push             # app   -> chatbook
git -C E:/Playground_Projects/05_ChatBook/harness push              # tasks -> harness
```
Push each newly accepted agent branch by its full name (the next push has the 4 P1 branches,
listed in 6.4), for example:
```
git -C E:/Playground_Projects/05_ChatBook/chatbook push origin agent/cb-31-likes--local-14b-arch--20261028-220013-d8d2
```
Then update `main`. From Git Bash:
```bash
bash E:/Playground_Projects/05_ChatBook/tools/publish-main.sh
```
From PowerShell, call Git's bash. Plain `bash` there starts WSL, which can't see `E:/`:
```powershell
& "C:\Program Files\Git\bin\bash.exe" E:/Playground_Projects/05_ChatBook/tools/publish-main.sh
```
On the original PC these remotes and push settings are already in place. Push only accepted
`agent/*` branches; rejected attempts stay local.

The publish script builds `main`'s tree straight from the three branch tips, so `main` always
matches them exactly. That holds even after a branch was rewritten or someone committed to
`main`. Each new tip becomes a merge parent, so `main`'s history keeps every commit. The script
works in a throwaway clone, never touches the local repos and never force-pushes. It pushes
nothing when `main` is already current.

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
**The owner chose (a) on 2026-10-28**, in 3 waves (section 1). P1 is done; P2 is next (6.4).

**(a) Polish wave.** Take the items in `notes/polish-backlog.md`. For each one:
1. Staff change the frame, or the stub CONTRACT and the DESIGN §6.5 spec.
2. Run `py tools/check_extra.py --write-contracts`.
3. Write a follow-up task with a new number (e.g. `cb-31-likes`; not `cb-24b`, because task
   selectors match prefixes). Carry the old acceptance tests into it, changing only the cases
   the new spec contradicts (never edit the old task folder), and add the new ones.
4. Validate it on the oracle.
5. Run it on `chatbook`.
6. Integrate with every branch in `harness/accepted.txt`. Once the new branch is accepted, it
   replaces its old one, which moves to the retired block. Until then the old branch stays
   listed. In the integrate itself, leave out only an old branch whose replacement passed
   (DESIGN 7.2 step 4).

A reopened feature is changed **in place**. Staff change only its CONTRACT block on `main`
(step 1), and the model edits its own code below it. The new hidden tests fail on the old code,
so the baseline check still holds. The prompt must say that the file always changes, and quote
the current body as "wrong now" next to the new one: an attempt that changes nothing gets no
test feedback. A staff commit that resets the file to its new CONTRACT stub is only the
fallback (DESIGN 8.1 step 4).

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
4. Integrate this wave's passing branches together with every branch in `harness/accepted.txt`
   (PowerShell):
   ```
   $keep = Get-Content E:/Playground_Projects/05_ChatBook/harness/accepted.txt |
           Where-Object { $_ -and -not $_.StartsWith('#') }
   swarm -t chatbook integrate $keep <this wave's passing>
   ```
   Check the line `integration OK: N branch(es) merged`, because a mistyped name is only
   logged as "ignored".
5. Check provenance with `git -C chatbook log --format=%b main..integration/<stamp>`. Every commit must be `local-*`, and no file may be outside `features/`.
6. Have the code reviewed by a multi-lens review with skeptic verification.
7. Run the browser smoke test.
8. `git -C chatbook merge --ff-only integration/<stamp>`, then `swarm -t chatbook clean`. Don't pass `--branches`: the accepted branches must stay.
9. In `harness/accepted.txt`, add the merged branches and move each replaced old branch to the
   retired block; commit the harness. Update `PROGRESS.md`.

### 6.4 Polish P1: done. Next: design P2
**P1 is done (2026-10-28).** The runbook was `notes/polish-p1-design.md` G.4, the specs are in
DESIGN 6.5 ("Polish P1"), and PROGRESS has the full record.
- Worker (`local-14b-arch`): 4/4 passed in 1 iteration each, 18.5 min in total; architect input
  4.8-5.1k tokens. Logs: `harness/runs/p1-cb31.log`, `p1.log`, `p1-integrate.log`.
- Integrate `integration/20261028-221919`: the 28 kept branches + the 4 P1 branches = 32
  merged. All gates and 1009 hidden tests are green. Provenance: 4 new commits, all
  `local-14b-arch`, only the 4 feature files.
- Code review `wf_c88636e8-22e`: 0 findings. The browser smoke (DESIGN 7.3 + design G.5)
  passed. The stale post-page case was not re-run; it goes to P2 (backlog item 8).
- `chatbook` `main` @ `b21aa4b`; harness `80cc90e` (`accepted.txt`); oracle @ `b21aa4b`.
- The 4 P1 branches (kept, to push with the next push):
  `agent/cb-31-likes--local-14b-arch--20261028-220013-d8d2`,
  `agent/cb-32-comments--local-14b-arch--20261028-220428-077a`,
  `agent/cb-33-activity--local-14b-arch--20261028-220843-27db`,
  `agent/cb-34-page_activity--local-14b-arch--20261028-221245-fb33`.

**Next step: design P2**, the same way as P1 (`notes/polish-p1-design.md` is the model).
1. A design workflow writes `notes/polish-p2-design.md` for the backlog items:
   - 12: confirm before delete, including the Activity page's Delete and Unlike buttons;
   - 8: busy buttons / a `CB.action` helper, including the stale post-page notes from P1;
   - 6 and 13: pre-wrap text for bios, posts and comments;
   - 4: stale badge after logout;
   - 7: polling after a failed first load.

   Items 3 and 5 are low and optional. The owner approves the design and answers its open
   questions. New task numbers start at cb-35.
2. Then the P1 steps: staff frame commit on `chatbook` `main`, this folder's docs, the harness
   commit (tasks + `accepted.txt`), validate on the oracle, worker runs, integrate from
   `accepted.txt` (6.3), provenance, code review, browser smoke, merge, update `accepted.txt`.
3. After P2: P3 paging (items 1, 2, 9, 14).

Nothing is pushed yet. Push only when the owner asks, then publish `main` with
`tools/publish-main.sh` (6.0).
