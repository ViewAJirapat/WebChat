# Report: how Claude made the local model write and fix ChatBook

This report explains how Claude (the chief) got **qwen2.5-coder 14B** to write all 30 ChatBook
features and fix its own mistakes. The model ran locally in Ollama on the GTX 1080 Ti. Every
example below is copied from the real run logs in `harness/runs/`. Those logs stay on this PC;
they are not pushed to GitHub.

## Short answer

- Claude never chatted with the model and never typed code for it.
- Each feature was a **task file** with a very exact spec. Claude ran one command,
  `swarm ... run <tasks>`, and the harness did the rest:
  1. it built the prompt;
  2. it started Aider with the model;
  3. it checked the result with gates and hidden tests.
- **Bug fixing was automatic.** When a check failed, the harness sent the error output back to
  the model and started a new attempt, up to 4 attempts per task. The error output was cut to fit
  3,000 characters.
- Twice something went wrong that the model could not fix itself. Both times Claude fixed the
  **inputs** and re-ran the model: the GPU setup, and a new gate after a code review. Claude never
  fixed the model's code by hand.

**Result:** 30 of 30 features were accepted:
- 24 on the first attempt;
- 5 on the second attempt;
- 1 on the third attempt.

This does not count the 6 Wave 1 runs that timed out on the CPU (section 6.3).

Section 7 shows real examples: how each error looked, the prompt that fixed it and the result,
plus one case (cb-05) where Claude had to step in.

### Words used in this report

| Word | Meaning |
|---|---|
| harness | The `swarm` program in `04_AgentSwarm`. It runs the model and checks its work. |
| frame | The base app that staff wrote: server, database, UI toolkit and docs. Features plug into it. |
| stub | An almost empty feature file that the model fills in. |
| CONTRACT block | The comment at the top of each stub that says exactly what to build. |
| gate | An automatic check that must pass: ruff, mypy, the frame tests, `check_extra.py` and the import rules. |
| hidden tests | Each task's acceptance tests. The model can never read them. |
| attempt | One try inside a task run. The harness allows up to 4 per task. The logs call an attempt an "iteration" ("iteration 2/4" = attempt 2 of 4). |
| worktree | A separate checkout of the repo, made for one run. |
| oracle | The staff's reference solution for a task. It is used only on a throwaway clone. |
| spec debt | Behaviour that is wrong but is exactly what the spec asked for. |

## 1. Who did what

| Role | Who | What they wrote |
|---|---|---|
| Owner | you | the goal and the rules |
| Chief | Claude (main session) | plans, `swarm` commands, review decisions, merges |
| Staff | Claude subagents in workflows | the frame (with 290 frame tests), the 30 task specs, 937 hidden tests and a reference solution for each task |
| Worker | qwen2.5-coder 14B through Aider | **all feature code**: 30 commits, 1,078 lines added |

The reference solutions were used only on a throwaway clone (`chatbook-oracle`). Before the
model ever saw a task, they proved three things:
- the task could be solved;
- its hidden tests fail on the empty stub;
- its hidden tests pass on a correct solution.

That is not proof that the tests are perfect: reviews later found weak tests in cb-28 and cb-29,
and they were fixed. The reference solutions never reached the real app. Every feature commit on
`main` says `Automated change by swarm engine local-14b-arch`, and Claude checked that before
each merge.

## 2. The chain of command

```
Claude (chief)
  |  swarm -t chatbook run cb-23 cb-24 ... -j 1      (swarm as defined in section 3)
  v
swarm harness (04_AgentSwarm, not modified for ChatBook)
  |  1. new worktree + branch agent/<task>--local-14b-arch--<time>
  |  2. writes prompt.md (task spec + rules + how the work is checked)
  v
Aider 0.86.2, architect mode
  |  call 1 "architect": reads the prompt and the files, describes the changes
  |  call 2 "editor":    gets only the architect's answer + the files, writes the whole file
  v
qwen2.5-coder:14b in Ollama (GPU, 8k context, ~17 tokens/s)
  |  edits one file: src/chatbook/features/<name>/handler.py or ui.js
  v
swarm harness checks
  |  autofix -> guard -> gates -> hidden tests
  |-- all pass -> commit on the agent/ branch, done
  '-- any fail -> feedback.md -> next attempt (at most 4)
```

`-j 1` runs one task at a time, because there is only one GPU.

## 3. The commands Claude typed

All commands use the harness with the ChatBook config:
`swarm` = `E:/Playground_Projects/04_AgentSwarm/.venv/Scripts/swarm.exe -c E:/Playground_Projects/05_ChatBook/harness/swarm.toml`.

| Step | Command | Why |
|---|---|---|
| Prove the new tasks | `swarm -t chatbook-oracle validate cb-23 cb-24 ... -j 2` | The reference solution must pass, and the hidden tests must fail on the empty stub. |
| Let the model work | `swarm -t chatbook run cb-01-accounts cb-02-people ... -j 1 > harness/runs/wave1-attempt2.log` | Runs one wave of tasks, one task at a time. (`wave1-attempt2.log` is the log of the second run of Wave 1.) |
| Merge a wave for testing | `swarm -t chatbook integrate <this wave's branches> <all earlier accepted branches>` | Merges the branches into a new `integration/` branch. It runs every gate again, plus every earlier hidden test as a regression check. |
| Check who wrote it | `git -C chatbook log --format=%b main..integration/<stamp>` | Every commit must come from `local-14b-arch`, and none from `oracle`. |
| Review | a code-review workflow (several reviewer agents), plus a click-through of the app in the browser | Done on the integration branch, before `main` moves. A problem found here could stop the merge, as it did for cb-05 (section 6.3). |
| Accept | `git -C chatbook merge --ff-only integration/<stamp>` | Moves `main` forward. This happened 4 times: after Waves 1, 2 and 3, then after Waves 4 and 5 together. |

The 30 tasks ran in 5 waves:

| Wave | Tasks | Run time (model + checks) |
|---|---|---|
| 1 | cb-01..cb-06 | 26 min |
| 2 | cb-07..cb-16 | 66 min |
| 3 | cb-17..cb-22 | 35 min |
| 4 | cb-23..cb-27 | 42 min |
| 5 | cb-28..cb-30 | 27 min |

The whole app took about 3 h 15 min of run time. About 2 h 57 min of that was the model itself.

## 4. What the model actually receives

For each attempt the harness writes `prompt.md` and starts a **new** Aider run with it. The model
sees three things:
1. Aider's own built-in instructions (4.1);
2. `prompt.md`:
   - the task spec (4.2);
   - the harness's text (4.3);
   - on a retry, the feedback (section 6);
3. the files (4.4).

### 4.1 Aider's built-in instructions

Aider adds these on its own. Seen in `aider.llm.txt`:
- **Architect call:** "Act as an expert architect engineer and provide direction to your editor
  engineer ... Just show the changes needed. DO NOT show the entire updated function/file".
- **Editor call:** "To suggest changes to a file you MUST return the entire content of the updated
  file". It also gets the exact format to use and a small example.

### 4.2 The task spec (from `harness/tasks/<id>/task.toml`)

Staff wrote this part. Here is an excerpt of task cb-24 (likes):

```
Implement the feature `likes` in `src/chatbook/features/likes/handler.py`. The file is a stub:
keep its CONTRACT docstring unchanged at the top of the file, its three @route lines and the
function names `like_post`, `unlike_post` and `list_likes`, and replace each
`raise HTTPError(501, ...)` with the implementation below.
...
In every route: pid = path_id(request); visible_post(db, pid, me)    (404)
  n = int(db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid)) after the change
POST /api/posts/{id}/like                                  function like_post
  db.run("INSERT OR IGNORE INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
         pid, me, request.now)
  -> 200 {"post_id": pid, "like_count": n, "liked": True}
...
Example: kim (id 1, "Kim Ko") and lee (id 2, "Lee Lo") are friends; lee wrote post 7 ...
  As kim, POST /api/posts/7/like -> 200 {"post_id": 7, "like_count": 1, "liked": true};
...
JSON keys, status codes and list order must match exactly; error message texts are not tested.
```

The spec is close to pseudo-code on purpose (see section 5).

### 4.3 The harness's own text (added to every prompt)

- **"How your work is checked"**: the 5 gate commands (ruff check, ruff format, mypy, the frame
  tests, `tools/check_extra.py`) and the import rules.
- **Hidden tests:** "Hidden acceptance tests for this task also run. You cannot see them, so
  implement exactly what the task describes, including the edge cases it mentions."
- **Autofix:** the fixers the harness runs before checking.
- **"Rules the harness enforces"**:
  - edits to protected paths are reverted;
  - added lines like `# noqa` or `# type: ignore` block the change;
  - the task may change only its own feature folder;
  - the model must not commit;
  - "nobody will answer questions".

### 4.4 The files

| File | How Aider gets it | Why |
|---|---|---|
| The stub, e.g. `features/likes/handler.py` | `--file` (editable) | The only file the model may change. It starts with its **CONTRACT** block, which is the spec condensed to about 30 lines (the longest, posts, has 33). |
| `docs/api/base.md` plus 0 to 2 domain docs (`social.md`, `chat.md`, `posts.md`); `docs/ui.md` for pages | `--read` (read-only) | The API the model codes against, with a style example. |
| `AGENTS.md` (copied as `rules.md`) | `--read` | 45 lines of house rules: imports, SQL style, mypy hints, banned JS. |
| Everything protected, including tests | hidden with `--aiderignore` | So Aider never adds them to the chat. |

The CONTRACT block matters because of how architect mode works. The editor call does **not** see
`prompt.md`: it sees only the architect's answer and the files. So the spec has to live inside
the file too, or the editor would write code without it.

### 4.5 How Aider is started

The model does not see this part. These are the important flags the harness passes (cb-24
example):

```
aider --model ollama_chat/qwen2.5-coder:14b --architect --map-tokens 0
      --message-file prompt.md --yes-always --no-auto-commits --no-auto-lint
      --no-suggest-shell-commands --chat-language English --timeout 300
      --model-settings-file config/aider.model.settings.yml   (num_ctx 8192, num_predict 4096)
      --read rules.md --file src/chatbook/features/likes/handler.py
      --read docs/api/base.md --read docs/api/posts.md
```

- `--message-file` + `--yes-always`: one request, run without anyone at the keyboard.
- `--no-auto-commits`, `--no-auto-lint`: the harness commits and lints, not Aider.
- `--map-tokens 0`: turns off Aider's repo map (its automatic summary of every file), to keep the
  8k context free for the task.
- `--chat-language English`: without it Aider follows the Windows locale and answers in Thai.
- `num_predict 4096`: stops a model that is stuck repeating itself.
- The Aider run of one attempt (both calls) is stopped after 900 s. The checks run after that,
  with their own time limits.

Tokens, measured over all 78 model calls of the project:
- **First attempts:** every architect call stayed under the 5.5k target (the largest was 5.2k).
- **Retries:** the feedback makes the prompt longer, and 4 retry calls went over the target. The
  largest, cb-23 attempt 2, sent 6.7k tokens and got 1.5k back: about 8.2k, right at the
  8,192-token limit.
- **Replies:** never more than 2.1k tokens.

## 5. How the specs were written for a 14B model

A 14B model with an 8k context does well on small, exact jobs and badly on vague ones. So staff
followed these rules (DESIGN.md section 0 rows 8 and 13, and sections 6.1, 6.4 and 7.2):

1. **One file per task**, at most ~120 lines, in its own feature folder. The model cannot break
   other features: edits outside the folder are reverted.
2. **Give the exact lines that are easy to get wrong:**
   - the SQL text for every join, filter and sort;
   - the exact JSON keys and status codes;
   - the order of the checks (which error wins);
   - every UI label, and the test id of every repeated control (for example one button per
     list row).
3. **A worked example with real numbers**, like the kim/lee one above. The hidden tests use
   *different* names and ids, so copying the example's values does not pass.
4. **Name the helpers to use.** The frame has helpers that raise the right error themselves
   (`path_id`, `visible_post`, `body_str`, ...), so the model writes fewer `if` branches.
5. **Make the frame forgive common habits.** For example, `db.one(sql, (rid,))` works as well as
   `db.one(sql, rid)`, because qwen writes the sqlite3 style out of habit.
6. **ASCII only in tested strings.** The architect may rewrite a character like "…" as "..." in
   its answer, and the editor copies that. A test expecting "…" would then fail.
7. **Keep it short.** Each task prompt is at most ~700 words. Wave 1 was a test run: Claude
   measured its token counts before running the rest.

## 6. How bugs were fixed

### 6.1 Automatic: the retry loop

After each attempt the harness does this, in order:
1. **Autofix:** puts back a CONTRACT block that was deleted, then runs `ruff --fix` and
   `ruff format`. Problems that ruff can fix by itself (spacing, quotes, import order) never reach
   the model. A string line that is too long cannot be fixed automatically, so that one does reach
   it (cb-23, cb-24).
2. **Guard:**
   - reverts edits outside the feature folder or to protected files;
   - blocks banned lines (`# noqa`, `# type: ignore`, skip markers, SQL in f-strings).
3. **Gates:**
   - ruff and mypy;
   - the 290 frame tests;
   - `check_extra.py`: JS syntax, banned DOM calls, the CONTRACT block unchanged, file size;
   - the import rules.
4. **Hidden tests:** the test files stay outside the model's checkout, so the model cannot read
   them. When a test fails, its name and a short error trace go into the feedback (sometimes with
   the failing `assert` line), because `swarm.toml` sets `acceptance_feedback = "full"`. That is
   why the test data uses names and ids that differ from the spec's example.

If anything fails, the harness writes `feedback.md`. It then starts the next attempt with the same
prompt plus a section **"Attempt N did not pass"**. Each attempt is a new Aider run, and the model
does not remember what it said before. It sees only its earlier code (still in the file) and this
feedback:
- The prompt says: "Fix the problems below and keep what already works."
- The output of each failed check is cut so that all of them fit in 3,000 characters.
- The checks that already pass are listed ("Already passing: ...") so the model leaves them alone.
- If an attempt produces exactly the same code as the attempt before, a "stuck" warning is added.
  This never happened in ChatBook.

Section 7 shows four of these retries step by step (the error, the fix prompt and the result),
plus the cb-05 case from 6.3, which no check caught.

### 6.2 Every retry in the project

| Task | Attempts | What failed first | How the model fixed it |
|---|---|---|---|
| cb-06 login page | 2 | A JS syntax error (`]);` at line 59), so the frame tests failed and the hidden tests went 0/16 | It fixed the syntax; everything passed. |
| cb-15 people page | 2 | It changed **one space** inside the CONTRACT comment. The gate printed "line 14 must be ... but is ...", with the full block | It restored the block exactly. |
| cb-17 inbox page | 2 | The same kind of mistake: one space removed in the CONTRACT comment | Restored. |
| cb-23 posts | 3 | It read the spec's shorthand `Notation: db = request.db, me = request.me.id` as code and used `db` and `me` as variables: 22 ruff errors, mypy errors, hidden tests failed | Attempt 2 fixed the names. One 150-character SQL line was left: it had been there from the start, but the cut feedback hid it until then. Attempt 3 split it (section 7, Example 2). |
| cb-24 likes | 2 | One 115-character SQL line | Split it into two strings (section 7, Example 1). |
| cb-28 feed page | 2 | It dropped the last 2 lines (28-29) of the CONTRACT comment | Restored them from the printed block. |

The other 24 tasks passed on the first attempt. In 3 of them (cb-10, cb-20, cb-21) the model had
deleted its CONTRACT block, and the autofix quietly put it back before the checks ran.

### 6.3 When Claude stepped in, without touching the model's code

| Problem | What Claude did |
|---|---|
| **Wave 1, first run: all 6 tasks timed out at 900 s.** Ollama had updated itself to 0.40.11 and fell back to the CPU, because its new CUDA 13 build drops the 1080 Ti (Pascal). | Claude restarted Ollama (`ollama.exe serve`) with `OLLAMA_LLM_LIBRARY=cuda_v12`. It then checked the GPU under load through Ollama's HTTP API (a `/api/generate` warm-up, then `/api/ps`): 88% GPU, 9.5 of 10.8 GB VRAM, 16.9 tokens/s. The second run passed 6/6 in 26 min. |
| **cb-05 friends deleted its own CONTRACT block.** Its code was right and every test passed, so no gate noticed. The code review did. | Staff added a CONTRACT gate to `check_extra.py`. Claude rejected that branch and re-ran cb-05 with the gate in place. It passed on the first attempt and kept the block on its own. At the same time, staff added the autofix step that puts a deleted block back, used from Wave 2 on. The gate later caught cb-15, cb-17 and cb-28 (6.2). |
| **cb-09: Aider applied a correct edit after about 3 minutes, then did not exit.** | The 900 s limit stopped it. The harness checked the edits anyway, they passed, and Claude watched for it to happen again (it did not). |
| **Reviews found behaviour that the spec itself required.** For example, after an unfriend a user can't delete their own comment on the ex-friend's post. | Recorded as spec debt in `notes/polish-backlog.md` and not blamed on the model. To fix one, staff would change the spec and tests, and the model would re-implement the feature. |

### 6.4 The escalation ladder (ready, but never used)

DESIGN.md 8.1 says what to do when a task fails all 4 attempts. Each step is tried only if the one
before it fails:
1. Read the feedback and the diff, and decide what kind of failure it is.
2. Re-run unchanged (the model's answers vary).
3. Sharpen the spec and the CONTRACT block, re-validate on the oracle, then re-run.
4. Split the task into smaller ones.
5. Try another engine:
   - `local-14b` (no architect step, so the single call sees the prompt directly);
   - `local-7b-arch` (16k context).
6. Ask the owner (for example, about a bigger model).

No task failed all 4 attempts, so this ladder was never used, and no spec had to be changed after
a failure. The re-runs in 6.3 had other causes: the GPU setup and a review.

## 7. Examples: the error, the fix prompt and the result

**Who writes the fix prompt?** The harness writes it automatically, not Claude. For a retry it
sends the model the **whole original prompt again** (the task spec and rules from section 4). At
the end it adds one "Attempt N did not pass" section with the errors of the attempt just before;
feedback from older attempts is not kept. In each example below,
"The fix prompt" shows only that added section, copied from `prompt.md` of the next attempt.

How to read the cuts in the examples:
- A line like `... [6293 chars omitted] ...` was cut by the harness to fit 3,000 characters. The
  model saw it exactly like that.
- A line like `[cut in this report: ...]` was left out only in this report.

### Example 1: a line that is too long (cb-24 likes, 2 attempts)

**What the model wrote (attempt 1).** The logic was right. The SQL is the spec's query, put on one
line:

```python
    rows = request.db.all(
        "SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id WHERE l.post_id = ? ORDER BY l.created_at, u.id",
        pid,
    )
```

**How the error looked to Claude**, in the wave log (`harness/runs/wave4.log`):

```
[cb-24-likes] iteration 1/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-24-likes]   ruff check=FAIL, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=ok
```

The hidden tests already passed (`acceptance=ok`); only the line-length rule failed.

**The fix prompt (added at the end of attempt 2's prompt), in full:**

````
## Attempt 1 did not pass
Your earlier changes are still in the working tree. Fix the problems below and keep what already works.

### FAILED: `python -m ruff check .` (exit 1)
```
E501 Line too long (115 > 100)
  --> src\chatbook\features\likes\handler.py:52:101
   |
50 |     visible_post(request.db, pid, request.me.id)
51 |     rows = request.db.all(
52 |         "SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id WHERE l.post_id = ? ORDER BY l.created_at, u.id",
   |                                                                                                     ^^^^^^^^^^^^^^^
53 |         pid,
54 |     )
   |

Found 1 error.
```

Already passing: `python -m ruff format --check .`, `python -m mypy src`, `python -m pytest -q -p no:cacheprovider tests`, `python tools/check_extra.py`, `architecture rules`
````

**The model's answer** (architect call, 192 tokens): "To fix the line too long error, we need to
split the SQL query into multiple lines."

**Result.** The model split the string into two adjacent literals:

```python
    rows = request.db.all(
        "SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id "
        "WHERE l.post_id = ? ORDER BY l.created_at, u.id",
        pid,
    )
```

```
[cb-24-likes] iteration 2/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-24-likes]   ruff check=ok, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=ok
[cb-24-likes] PASSED in 2 iteration(s); commit da844d09a2 on agent/cb-24-likes--local-14b-arch--20261028-014937-36e3
```

All 44 hidden tests passed. Total time: 7 min 10 s.

### Example 2: names that don't exist, then a long line (cb-23 posts, 3 attempts)

**What the model wrote (attempt 1).** The spec and the CONTRACT block use the shorthand
`Notation: db = request.db, me = request.me.id.`. The model used `db` and `me` as if they were
real variables, but never created them:

```python
def create_post(request: Request) -> Response:
    text = body_str(request, "body", max_len=2000)
    pid = db.run(
        "INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", me, text, request.now
    )
    return Response(201, {"post": post_json(db, visible_post(db, pid, me), me)})
```

**How the error looked to Claude:**

```
[cb-23-posts] iteration 1/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-23-posts]   ruff check=FAIL, ruff format=ok, mypy src=FAIL, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=FAIL
```

**The fix prompt (added at the end of attempt 2's prompt), in full.** This one shows how the
harness cuts long output. ruff had 22 errors (21 undefined names and 1 long line) and the hidden
tests had 41 failures, so most of it was cut to fit 3,000 characters.

````
## Attempt 1 did not pass
Your earlier changes are still in the working tree. Fix the problems below and keep what already works.

### FAILED: `python -m ruff check .` (exit 1)
```
F821 Undefined name `db`
  --> src\chatbook\features\posts\handler.py:71:11
   |
69 | def create_post(request: Request) -> Response:
70 |     text = body_str(request, "body", max_len=2000)
71 |     pid = db.run(
   |           ^^
72 |         "INSERT INTO posts (author_id, body, created_at) VALUES (
... [6293 chars omitted] ...
> src\chatbook\features\posts\handler.py:106:5
    |
104 |         raise HTTPError(403, "forbidden")
105 |     db.run("DELETE FROM likes WHERE post_id = ?", pid)
106 |     db.run("DELETE FROM comments WHERE post_id = ?", pid)
    |     ^^
107 |     db.run("DELETE FROM posts WHERE id = ?", pid)
108 |     return Response(200, {"deleted": pid})
    |

F821 Undefined name `db`
   --> src\chatbook\features\posts\handler.py:107:5
    |
105 |     db.run("DELETE FROM likes WHERE post_id = ?", pid)
106 |     db.run("DELETE FROM comments WHERE post_id = ?", pid)
107 |     db.run("DELETE FROM posts WHERE id = ?", pid)
    |     ^^
108 |     return Response(200, {"deleted": pid})
    |

Found 22 errors.
```

### FAILED: `python -m mypy src` (exit 1)
```
src\chatbook\features\posts\handler.py:71: error: Name "db" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:72: error: Name "me" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:74: error: Name "db" is not defined  [name-defined]
src\chatbook\features\posts
... [786 chars omitted] ...
ined]
src\chatbook\features\posts\handler.py:96: error: Name "me" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:102: error: Name "db" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:102: error: Name "me" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:103: error: Name "me" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:105: error: Name "db" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:106: error: Name "db" is not defined  [name-defined]
src\chatbook\features\posts\handler.py:107: error: Name "db" is not defined  [name-defined]
Found 19 errors in 1 file (checked 64 source files)
```

### FAILED: hidden acceptance tests (30/71 passed)
```
FFFFFFFFFFFFFFFFFFFFFFF........FFFFFF.............FFFFFF.....FFFFFF....  [100%]
================================== FAILURES ===================================
_____ test_feed_has_own_and_friends_posts_newest_first_with_exact_shapes ______
..\..\..\runs\cb-23-posts--local-14b-arch--20261028-012459-5
... [53585 chars omitted] ...
is_404[4] - NameErro...
FAILED test_cb23_posts.py::test_get_post_after_unfriend_is_404 - NameError: n...
FAILED test_cb23_posts.py::test_get_unknown_or_bad_post_id_is_404[999] - Name...
FAILED test_cb23_posts.py::test_author_deletes_post_with_its_likes_and_comments
FAILED test_cb23_posts.py::test_friend_cannot_delete_post_is_403 - NameError:...
FAILED test_cb23_posts.py::test_non_friend_delete_is_404[2] - NameError: name...
FAILED test_cb23_posts.py::test_non_friend_delete_is_404[4] - NameError: name...
FAILED test_cb23_posts.py::test_deleting_a_post_without_likes_or_comments - N...
FAILED test_cb23_posts.py::test_delete_unknown_or_bad_post_id_is_404[999] - N...
41 failed, 30 passed in 2.06s
```

Already passing: `python -m ruff format --check .`, `python -m pytest -q -p no:cacheprovider tests`, `python tools/check_extra.py`, `architecture rules`
````

**The model's answer:** "we need to ensure that the `db` and `me` variables are properly defined
and accessible within the functions ... Add `db = request.db` and `me = request.me.id` at the
beginning of each function where they are used."

**Result of attempt 2.** The names were fixed in every function:

```python
def create_post(request: Request) -> Response:
    db = request.db
    me = request.me.id
    text = body_str(request, "body", max_len=2000)
```

mypy and all 71 hidden tests now passed. ruff still failed on one 150-character SQL line in
`get_feed`. That line was not new: it was already in attempt 1, as one of the 22 ruff errors.
But it sat inside the `... [6293 chars omitted] ...` part, so the model never saw it until now.
Cutting the feedback saved context, but here it cost one extra attempt.

```
[cb-23-posts] iteration 2/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-23-posts]   ruff check=FAIL, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=ok
```

**The fix prompt for attempt 3, in full:**

````
## Attempt 2 did not pass
Your earlier changes are still in the working tree. Fix the problems below and keep what already works.

### FAILED: `python -m ruff check .` (exit 1)
```
E501 Line too long (150 > 100)
  --> src\chatbook\features\posts\handler.py:87:101
   |
85 | …
86 | …
87 | …? OR author_id IN (SELECT friend_id FROM friendships WHERE user_id = ?)) ORDER BY id DESC",
   |                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
88 | …
89 | …
   |

Found 1 error.
```

Already passing: `python -m ruff format --check .`, `python -m mypy src`, `python -m pytest -q -p no:cacheprovider tests`, `python tools/check_extra.py`, `architecture rules`
````

**The model's answer:** "To fix the line too long error, we need to split the long SQL query into
multiple lines."

**Final result (attempt 3):**

```python
    rows, more = db.page(
        "SELECT * FROM posts WHERE id < ? AND (author_id = ? OR author_id IN "
        "(SELECT friend_id FROM friendships WHERE user_id = ?)) ORDER BY id DESC",
        cursor,
        me,
        me,
        limit=limit,
    )
```

```
[cb-23-posts] iteration 3/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-23-posts]   ruff check=ok, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=ok
[cb-23-posts] PASSED in 3 iteration(s); commit 31f2e1cec4 on agent/cb-23-posts--local-14b-arch--20261028-012459-5205
```

All 71 hidden tests passed. Total time: 24 min 38 s, the longest task in the project.

### Example 3: a JavaScript syntax error (cb-06 login page, 2 attempts)

**What the model wrote (attempt 1).** The page's `render` is a value inside the object given to
`CB.page(...)`, so it must end with `,` or nothing. The model ended it with `;`:

```javascript
CB.page('login', {
  title: 'Welcome',
  public: true,
  render: () => CB.el('div', {class: 'stack narrow'}, [
    CB.el('h2', {}, 'Log in'),
    [cut in this report: the two forms and the 'Create account' heading, 31 lines]
  ]);
});
```

**How the error looked to Claude** (`harness/runs/wave1-attempt2.log`):

```
[cb-06-page_login] iteration 1/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-06-page_login]   ruff check=ok, ruff format=ok, mypy src=ok, pytest=FAIL, python tools/check_extra.py=FAIL, architecture=ok, acceptance=FAIL
```

One character broke three checks: the page could not load at all, so every hidden test failed.

**The fix prompt (added at the end of attempt 2's prompt), in full:**

````
## Attempt 1 did not pass
Your earlier changes are still in the working tree. Fix the problems below and keep what already works.

### FAILED: `python -m pytest -q -p no:cacheprovider tests` (exit 1)
```
........................................................................ [ 25%]
...............................F........................................ [ 51%]
.F...................................................................... [ 76%]
............................................................
... [565 chars omitted] ...
run_page_defaults_to_the_feature_ui_file ________________

    def test_run_page_defaults_to_the_feature_ui_file() -> None:
        res = run_page("page_login", None, me=None)
>       assert res.errors == []
E       assert ['Unexpected ...login.js:59)'] == []
E         
E         Left contains one more item: "Unexpected token ';' (at /ui/page_login.js:59)"
E         Use -v to get more diff

tests\test_testing.py:379: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_route_map.py::test_all_ui_files_load_together_without_errors
FAILED tests/test_testing.py::test_run_page_defaults_to_the_feature_ui_file
2 failed, 280 passed in 8.71s
```

### FAILED: `python tools/check_extra.py` (exit 1)
```
src/chatbook/features/page_login/ui.js:59: SyntaxError: Unexpected token ';' (fix: fix the JavaScript syntax at that line)
      ]);
        ^
check_extra: 1 problem(s)
```

### FAILED: hidden acceptance tests (0/16 passed)
```
FFFFFFFFFFFFFFFF                                                         [100%]
================================== FAILURES ===================================
_______________ test_page_is_public_titled_welcome_without_nav ________________
..\..\..\runs\cb-06-page_login--local-14b-arch--20261027-175
... [8679 chars omitted] ...
essage_and_stays[400]
FAILED test_cb06_page_login.py::test_failed_create_account_shows_the_server_message_and_stays[409]
FAILED test_cb06_page_login.py::test_failed_create_account_shows_the_server_message_and_stays[400]
FAILED test_cb06_page_login.py::test_log_in_can_be_retried_after_a_failure - ...
FAILED test_cb06_page_login.py::test_empty_fields_are_sent_without_checks[Log in-/api/auth/login-body0]
FAILED test_cb06_page_login.py::test_empty_fields_are_sent_without_checks[Create account-/api/auth/register-body1]
FAILED test_cb06_page_login.py::test_each_form_sends_only_its_own_fields - as...
FAILED test_cb06_page_login.py::test_lives_in_its_own_feature_folder - Assert...
16 failed in 1.23s
```

Already passing: `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy src`, `architecture rules`
````

The most useful line is the gate's hint, which names the line, the character and what to do:
`ui.js:59: SyntaxError: Unexpected token ';' (fix: fix the JavaScript syntax at that line)`.

**The model's answer:** "Fix the Syntax Error: Remove the unexpected semicolon (`;`) at the end of
the `CB.page` call." It named the wrong place (the `;` it removed ends `render`, not
`CB.page`), but its code change was right.

**Result:** `]);` became `])`.

```
[cb-06-page_login] iteration 2/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-06-page_login]   ruff check=ok, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=ok
[cb-06-page_login] PASSED in 2 iteration(s); commit 1ac16399e6 on agent/cb-06-page_login--local-14b-arch--20261027-175413-9596
```

All 16 hidden tests passed. Total time: 7 min 4 s.

### Example 4: one space changed in the CONTRACT block (cb-15 people page, 2 attempts)

**What the model wrote (attempt 1).** The page worked, and all hidden tests passed. But in the
CONTRACT comment at the top of the file, the model removed one space from line 14:

```diff
-//                 CB.el('span', {class: 'muted'}, '@' + u.username), action(u))
+//                CB.el('span', {class: 'muted'}, '@' + u.username), action(u))
```

**How the error looked to Claude** (`harness/runs/wave2b.log`):

```
[cb-15-page_people] iteration 1/4: running local-14b-arch (ollama_chat/qwen2.5-coder:14b)
[cb-15-page_people]   ruff check=ok, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=FAIL, architecture=ok, acceptance=ok
```

**The fix prompt (added at the end of attempt 2's prompt).** The gate prints the line that is
wrong, what it must be, and the whole block to copy back:

````
## Attempt 1 did not pass
Your earlier changes are still in the working tree. Fix the problems below and keep what already works.

### FAILED: `python tools/check_extra.py` (exit 1)
```
src/chatbook/features/page_people/ui.js:14: CONTRACT block missing or changed (fix: restore it verbatim at the top of the file, then put your code below it)
    line 14 must be "//                 CB.el('span', {class: 'muted'}, '@' + u.username), action(u))" but is "//                CB.el('span', {class: 'muted'}, '@' + u.username), action(u))"
    the file must begin with these 25 lines, exactly as shown:
==== CONTRACT block of src/chatbook/features/page_people/ui.js ====
// page_people: search people and act on each result.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('people', {title: 'People', nav: 'People', order: 30, load, render})
[cut in this report: lines 4 to 23 of the block]
// Server answers: GET /api/users -> {users: [{id, username, display_name, relationship}]};
// POST /api/dm -> {conversation: {id, ...}}.
==== end of the CONTRACT block: your code goes below it ====
check_extra: 1 problem(s)
```

Already passing: `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy src`, `python -m pytest -q -p no:cacheprovider tests`, `architecture rules`
````

**The model's answer:** "restore the CONTRACT block verbatim and then place the implementation code
below it."

**Result:** the block was back exactly as the frame has it, and the code was unchanged.

```
[cb-15-page_people]   ruff check=ok, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=ok
[cb-15-page_people] PASSED in 2 iteration(s); commit 41889ffbf7 on agent/cb-15-page_people--local-14b-arch--20261027-201031-086e
```

All 10 hidden tests passed. The same gate also caught cb-17 (one space removed, like here) and
cb-28 (the last two lines of its block deleted). Both were fixed the same way on the retry.

### Example 5: a mistake no check caught, so Claude stepped in (cb-05 friends)

**What the model wrote.** In Wave 1 the model deleted the whole CONTRACT docstring at the top of
`features/friends/handler.py`, which starts like this:

```diff
-"""friends: list friends and unfriend.
-
-CONTRACT (keep this docstring; implement exactly this):
-Notation: db = request.db, me = request.me.id.
-GET /api/friends
[cut in this report: 10 more deleted lines]
```

Its code was correct. Every gate and every hidden test passed, so the harness committed it.

**How the error showed up.** Not in any log: the code review workflow that Claude runs after each
wave found it. A deleted block is a real problem, because a later retry on that file would run
without its spec (section 4.4).

**What Claude did.** Claude did not write a new prompt and did not edit the code:
1. Staff added a CONTRACT gate to `tools/check_extra.py` (chatbook `5208359`) and re-validated all
   22 tasks with it.
2. Claude re-ran the task with the **same prompt** as before (the two `prompt.md` files are
   identical):
   `swarm -t chatbook run cb-05 -j 1 > harness/runs/cb05-rerun.log`
3. After the re-run passed and Wave 1 was merged, Claude deleted the rejected branch:
   `git -C chatbook branch -D agent/cb-05-friends--local-14b-arch--20261027-175127-c731`

**Result:** this time the model kept the block on its own, and it passed on the first attempt.

```
[cb-05-friends]   ruff check=ok, ruff format=ok, mypy src=ok, pytest=ok, python tools/check_extra.py=ok, architecture=ok, acceptance=ok
[cb-05-friends] PASSED in 1 iteration(s); commit bce01b8c96 on agent/cb-05-friends--local-14b-arch--20261027-184618-e210
```

Total time: 3 min 36 s. From then on the gate caught this kind of mistake automatically, as in
Example 4.

## 8. Numbers

| | |
|---|---|
| Features accepted | 30 / 30, all written by qwen2.5-coder 14B |
| Accepted on attempt 1 / 2 / 3 | 24 / 5 / 1 |
| Model runs | 37 in total: 31 passed (one of them, the Wave 1 cb-05 run, was rejected by review) and 6 timed out on the CPU |
| Hidden tests | 937, all passing on the final `main` (`87de89e`) |
| Code from the model | 30 commits, 1,078 lines added |
| Run time | about 3 h 15 min over 5 waves, of which the model took about 2 h 57 min |
| One attempt (model only) | 1 to 10 min, median about 4 min (cb-09 hung until the 15-min limit after finishing its edit) |
| Tokens per call | 3.0k to 6.7k in, at most 2.1k out |

## 9. What made it work

These are judgments from this one project. No run compared them with other approaches.

1. **Exact specs worked.** Every spec gave the SQL, the JSON and the check order outright, and 24
   of the 30 tasks passed on the first attempt. The shorthand `db = request.db` appears in all 18
   backend specs, and the model read it as code only once (cb-23).
2. **Machine feedback was enough to fix the bugs.** The model fixed every gate and test failure
   from the error text alone, in one or two more attempts. It never needed an explanation from a
   person or from Claude. One limit: when the output is cut to fit the context, an error can be
   hidden for an attempt (section 7, Example 2).
3. **Put the spec inside the file.** The architect's second call never sees the prompt. The
   CONTRACT block is how the spec reaches it.
4. **Hidden tests keep the model honest.** It cannot read or edit them, only their failure
   messages. The test values differ from the examples, and tricks for skipping tests are blocked.
   So a pass means the code does what the spec says, as far as the tests check. Code review still
   found some wrong behaviour, but every case came from the specs, not from the model's mistakes
   (section 6.3, `notes/polish-backlog.md`).
5. **Check the infrastructure first.** The only total failure (6 timeouts) came from the GPU
   setup, not the model.

## Where to look for more

- The raw prompt, the model's replies and the feedback of any attempt are in
  `harness/runs/<run-id>/iter-N/`: `prompt.md`, `aider.chat.md`, `aider.llm.txt`, `feedback.md`
  and `diff.patch`.
- The prompt and feedback builders are in `04_AgentSwarm/swarm/runner.py` (`build_prompt`,
  `build_feedback`).
- The Aider command line is in `04_AgentSwarm/swarm/engines.py` (`AiderEngine.run`).
- The spec rules are in `DESIGN.md` section 0, sections 6.1 and 6.4, and section 8.1.
- The step-by-step log is in `PROGRESS.md`.
