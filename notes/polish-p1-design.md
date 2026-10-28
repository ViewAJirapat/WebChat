# Polish wave P1: final design (backlog items 10(a) and 11, plus "My activity")

Date: 2026-10-28. Status: design only. Nothing was changed in `chatbook`, `harness` or
`04_AgentSwarm`. No swarm command was run.

This design merges three drafts (lenses: worker-fit = W, privacy = P, harness = H). Each choice
below says which draft it follows and why.

## Summary

- **Reopen likes and comments in place.** Staff change only the CONTRACT docstring of
  `likes/handler.py` and `comments/handler.py` on `main`. The local model then edits its own code
  below the block. Two new tasks do this: **cb-31-likes** and **cb-32-comments**.
- **Two new features from stubs:** **cb-33-activity** (`GET /api/activity/hidden`) and
  **cb-34-page_activity** (page `activity`, title "My activity", nav "Activity" at order 45).
- **One new frame helper:** `can_see_post(db, post_id, viewer_id) -> bool`.
- **Item 11:** every "missing or hidden" 404 on the like and comment routes is exactly
  `{"error": "post not found"}`.
- **Old tests:** only 2 old cases contradict the owner's decision. They are **not edited**. cb-31
  and cb-32 carry the old suites (with those 2 cases changed). The regression list becomes a
  file, `harness/accepted.txt`. An old branch (cb-24, cb-25) leaves it only when its replacement
  is accepted, so likes and comments always have a regression suite.
- **Merge rule:** the page cb-34 merges only together with cb-31, cb-32 and cb-33.

**Checked in a scratch clone (no repo file touched):**
- The exact frame commit of section E passes every gate: ruff, ruff format, mypy, 291 frame tests
  and `check_extra` (after `--write-contracts`: 2 added, 2 changed, 0 removed).
- On that base, the old cb-24/cb-25 suites pass (104 tests) and draft new tests fail. So the
  baseline check holds for the in-place tasks.
- With reference code below the new blocks, the CONTRACT gate still passes. All 30 old hidden
  suites then give **935 passed, exactly 2 failed** (the 2 cases named in F).
- The reference activity handler is 75 lines after `ruff format`, with no line over 100. The
  reference page is 50 lines and runs clean in `run_page`.
- Changed after the trial (docstring text only, so the gates run again at G.4 step 3): the
  Notation line of the likes and comments blocks (E.2 items 7-8, 99 characters, under the
  100 limit). Block sizes stay 24 and 26 lines.

Scratch files (for staff, not part of any repo):
`C:\Users\viewj\AppData\Local\Temp\claude\E--Playground-Projects-04-AgentSwarm\5b7c77a6-caac-4525-89de-62c300d46dfa\scratchpad\p1check`
(`blocks\*.txt` = the 4 CONTRACT texts, `apply_frame.py` = the frame commit as a script,
`frame\` = the trial clone with reference code in its working tree, `v2\` = reference code).

---

## Decisions

| # | Decision | Choice | Why (and how the drafts disagreed) |
|---|---|---|---|
| 1 | How to reopen likes and comments | **In place** (all 3 drafts) | Every task's base is `main`, so the HANDOFF 6.2 stub reset would have to land on `main` itself: likes and comments would answer 501 for the whole wave, and stay broken if a task fails. In place keeps `main` working. The baseline check still holds, because the new tests fail on the old code (checked). DESIGN 8.1 step 4 already describes reopening a folder this way. Stub reset stays as the fallback. |
| 2 | Order of steps in unlike | **Delete my row first, then check visibility** (H) | One DELETE statement instead of two (W) or a SELECT plus a DELETE (P). It is the smallest edit of the existing function: drop one line, add four. When the answer is 404, nothing was deleted anyway (and the app rolls back every 4xx). |
| 3 | Unlike answer on a hidden post | **Leave out `like_count`**: `{"post_id": pid, "liked": False}` (W, P) | H proposed `"like_count": None`. No page reads the unlike answer (the feed and post pages only call `CB.refresh()`, checked). Leaving the key out is shorter for the worker and leaks nothing. |
| 4 | Delete own comment | **The comment's author may always delete it.** Other users keep the old checks (all 3) | Owner decision (a). |
| 5 | Item 11 text | **`"post not found"`** for a missing comment too (W, H) | P proposed keeping `"comment not found"` and adding a `can_see_post` check. Our choice is one changed literal, no new import, and one rule for the whole posts domain. It is also the fix the backlog itself proposed. Cost: Delete on a comment that is already gone toasts "post not found": a double click, or (on page_post) a comment the post's author deleted while the page was open. Known P1 behaviour (H); P2 notes next to items 8 and 12. |
| 6 | New helper | **`can_see_post` in `core/social.py`; `visible_post` stays byte for byte** (W, H) | P proposed rewriting `visible_post` on top of it. Not needed; leaving it alone has zero risk for 7 features that call it. |
| 7 | Activity route | **`GET /api/activity/hidden`, function `hidden_activity`** (W, H) | P proposed `/api/activity`. The name says what it lists, and keeps `/api/activity` free for later. |
| 8 | Activity contents | **Only my own rows on posts I can no longer see. At most 100 per list, no paging, no `has_more`** (W, H) | P added `has_more` via `db.page` and a UI note. More tests and more code for a case (100+ hidden items) that is very unlikely. Deleting items brings older ones into view. |
| 9 | SQL style in the activity CONTRACT | **Inline `db.all(...)` with adjacent literals, alias `AS post_author_id`, and "write `db` and `me` first" inside the block** (W style + H alias) | P proposed module-level SQL constants and a helper function. Inline SQL matches all 30 existing handlers. The alias stops the model from confusing the comment's author with the post's author. The "write db and me first" line fixes cb-23's first failure (undefined `db`/`me`). Measured: no line over 100 after `ruff format`. |
| 10 | Page layout | **Comments first, then likes; headings with counts; full comment body** | The owner's own words are "your comments and likes" (H's order). Counts in headings match page_post (P, H). W and P put likes first; P cut the body to 80 characters. A full body is simpler and the row wraps (`.item` has `overflow-wrap: anywhere`). A heading counts the listed rows, so it shows at most 100 (Decision 8); this is in "Defaults taken" for the owner. |
| 11 | Page texts | `You commented on a post by`, `You liked a post by`, empty texts `No comments to remove` / `No likes to remove` (W, P) | H's "No hidden comments" reads as if the comments were hidden. |
| 12 | Old hidden tests | **Supersede** (H): carry the old suites into cb-31/cb-32 with the 2 cases changed; retire each old branch once its replacement is accepted; integrate from `harness/accepted.txt` | W and P proposed editing the 2 cases inside the old suites. Superseding: (1) is the plan in HANDOFF 6.2 step 6 ("the new branch replaces its old one") and DESIGN 8.1 step 4; (2) keeps the HANDOFF 3 rule "never edit task acceptance folders"; (3) scales to P2/P3, which reopen pages whose old suites will contradict much more; (4) a mistake is loud: a listed retired branch fails integrate on exactly 2 known cases. An old branch retires only when its replacement is accepted (G.4 steps 9 and 11): `integrate` runs only the suites of the branches it merges, so retiring early would leave a held-back feature with no regression suite. Editing the old suites is the fallback (owner question 1). |
| 13 | AGENTS.md | **Add one bullet** about changing a working feature (P, H) | AGENTS.md is passed with `--read`, so it reaches the editor pass, which never sees the task prompt. Today it says only "edit the stub". |
| 14 | Error-text rule | **DESIGN 3.1 gets one exception** (W, H) | Today hidden tests never check error texts. Item 11 needs two error bodies to be equal. Tests compare the two bodies with each other, never with a literal. |
| 15 | Task ids | **cb-31 .. cb-34** (all 3) | `cb-24b` would make the selector `cb-24` ambiguous (`task.find_tasks` matches prefixes). |
| 16 | Run order | **cb-31 alone first, then cb-32 cb-33 cb-34 with `-j 1`** (W, P) | In-place editing is new for this model. One small task first shows its diff and token use. |
| 17 | Merge rule | **Merge cb-34 only together with cb-31, cb-32 and cb-33** (new) | The hidden tests are independent (cb-34's tests mock the API, so it can pass alone), but the product is not. Without cb-33, the page's `load` gets the stub's 501: a toast and an error card for every user on every visit, worse than today's "Coming soon". Without cb-31/cb-32, its Unlike and Delete buttons answer 404 on hidden posts. |
| 18 | swarm.toml | **No change** (all 3) | Same base, gates, autofix, protected paths and architecture rules. The new folders match `chatbook.features.*`. |
| 19 | In-place prompts | **Quote the current body as "wrong now" and the new body** in the cb-31 and cb-32 prompts; the Notation line of both reopened blocks says the code writes `request.db` and `request.me.id` (review) | When an attempt changes nothing, the runner skips the gates and the hidden tests (`if report.changes:`). The feedback is then only "No file changes remain", and an empty diff never counts as stuck. So the prompt alone must show that the file has to change. The Notation hint reaches the editor pass, which never sees the prompt (cb-23 lost an iteration to undefined `db`/`me`). |

---

## A. Item 10(a): the API rules

Notation (as in every spec): `db = request.db`, `me = request.me.id`. A post is **hidden** from
me when it exists and its author is neither me nor a friend of me.

### A.1 `DELETE /api/posts/{id}/like` (likes, function `unlike_post`)

Steps, in this order:
1. `pid = path_id(request)`. A bad id gets 404 from the frame (unchanged).
2. `gone = db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, me)`.
   `db.run` returns the number of rows deleted (0 or 1; checked in `core/store.py`).
3. If `not can_see_post(db, pid, me)` (the post is missing or hidden):
   - `gone == 0` -> `raise HTTPError(404, "post not found")` (exactly the 404 of `visible_post`);
   - else -> `200 {"post_id": pid, "liked": False}` (no `like_count`).
4. Else (I can see the post, unchanged): `n = COUNT(*)` after the delete ->
   `200 {"post_id": pid, "like_count": n, "liked": False}`.

| Case | Before | After |
|---|---|---|
| Visible post, my like / no like of mine | 200 with count | same (unchanged, still idempotent) |
| Hidden post (ex-friend or never a friend), my like | 404, like kept | **200 `{"post_id", "liked": false}`**, only my like of this post removed |
| The same request again | 404 | 404 `post not found` |
| Hidden post, no like of mine | 404 `post not found` | 404 `post not found` (same body as a missing post) |
| Missing post (also: post deleted by its author, which deletes its likes) | 404 | 404 (unchanged) |
| Friends again after an unfriend | - | the visible path: 200 with count |

On a hidden post the first call answers 200 and later calls 404. Answering 200 every time would
let anyone probe whether hidden posts exist.

`POST /api/posts/{id}/like` and `GET /api/posts/{id}/likes` do not change. `visible_post` comes
first, so a hidden post gives 404 even if I still have a like on it.

### A.2 `DELETE /api/comments/{id}` (comments, function `delete_comment`)

1. `cid = path_id(request)`; `row = db.one("SELECT * FROM comments WHERE id = ?", cid)`.
2. `row is None` -> `raise HTTPError(404, "post not found")` (item 11; was "comment not found").
3. If `row["author_id"] != me`:
   - `post = visible_post(db, row["post_id"], me)` (404 `post not found` if hidden);
   - `post["author_id"] != me` -> 403.
4. `db.run("DELETE FROM comments WHERE id = ?", cid)` -> `200 {"deleted": cid}`.

| Case | Before | After |
|---|---|---|
| My comment, visible post | 200 | 200 |
| My comment, hidden post (after an unfriend) | 404 | **200** |
| My comment, deleted twice | 404 the second time | 404 `post not found` |
| Not mine, hidden post | 404 `post not found` | same |
| Missing or already deleted id | 404 `comment not found` | **404 `post not found`** |
| Not mine, visible, I wrote the post | 200 | 200 |
| Not mine, visible, I did not write the post | 403 | 403 (I can read that comment anyway) |
| Bad id (`abc`, `0`) | 404 from `path_id` | same |

`GET` and `POST /api/posts/{id}/comments` do not change: 404 on a hidden post.

### A.3 What can leak

| Information | After P1 |
|---|---|
| Like count of a hidden post | never returned (no `like_count` key; activity has no counts) |
| Body of a hidden post | never returned (activity never selects `p.body`) |
| Other users' likes and comments on a hidden post | never returned (activity lists only my rows) |
| Whether a hidden comment id exists | not any more: same body as a missing id (item 11) |
| Whether a hidden post still exists | only for posts **I** liked or commented on. My row exists only while the post exists, so a 200 tells me the post (and my comment) is still there. This comes with option (a) plus the page. Low. |
| The ex-friend's display name | shown on the page; already public (people search, profiles) |

Not closed by P1 (owner chose (a), not (b)): the ex-friend and their friends keep seeing my like
or comment until I remove it. The new page is how I remove it.

---

## B. Item 11: one 404 for hidden and missing

- **Comments:** a missing comment now raises the same `HTTPError(404, "post not found")` that
  `visible_post` raises for a hidden one.
- **Likes:** POST and GET already use `visible_post` for both cases. The new hidden branch of
  DELETE raises the same text.
- **Other post routes** (`/api/posts/{id}`, comments GET and POST) go through `visible_post`
  already. No change.
- `path_id`'s 404 (`"not found"`) stays different. It depends only on the id's format.
- **Tests:** compare the hidden answer with the missing answer, `(status, json)`, never with a
  literal. For likes, a missing post and a hidden post without my like reach the same `raise` in
  `unlike_post`, so DELETE compared with DELETE would pass any text. The cb-31 tests therefore
  also compare the DELETE body with a body that `visible_post` itself produces in the same
  feature (`POST /api/posts/9999/like`, `GET /api/posts/<hidden>/likes`).
- **DESIGN 3.1 exception** (new text): "Hidden tests never assert error texts, with one exception:
  where a spec says two errors must look the same (a hidden thing and a missing thing), a test
  compares the two error bodies with each other."
- **Prompts:** cb-31 and cb-32 must not end with the usual "error message texts are not tested"
  alone. They say: "except this one: these 404 answers must be exactly
  HTTPError(404, "post not found")".
- **Frame guard:** the new `test_can_see_post` pins `visible_post`'s `(404, "post not found")`,
  because two features now copy that literal.

---

## C. The activity API (new feature `activity`, task cb-33)

- **Route:** `GET /api/activity/hidden`, not public (the frame answers 401 when logged out), no
  parameters, read-only.
- **Lists:** only my own comments and likes on posts I can no longer see: the post exists (inner
  JOIN) and its author is neither me nor a friend of me. `p.author_id != ?` is needed: I am not
  in my own friend list, so without it my own posts would count as hidden.
- **Answer:**
  ```
  200 {"comments": [{"id": int, "post_id": int, "post_author": U, "body": str, "created_at": int}],
       "likes":    [{"post_id": int, "post_author": U, "created_at": int}]}
  ```
  `body` and `created_at` of a comment item are **my comment's**. `created_at` of a like item is
  the like's time. A like has no id: `post_id` is its key.
- **Order:** comments by `c.id DESC`; likes by `l.created_at DESC, l.post_id DESC`.
- **Limit:** `LIMIT 100` in each SQL, no cursor, no `has_more`.
- **Never:** the post's body, its counts, any other post field, or other users' rows.
- **Tables read:** comments, likes, posts, friendships, users. Writes nothing.
- The visibility rule is SQL (the same rule as the cb-23 feed query), so the limit is exact and
  there are no per-row visibility queries. Tests pin that it agrees with `can_see_post`.

**Stub `src/chatbook/features/activity/handler.py`** (block: 24 lines, longest line 91):
```python
"""activity: my comments and likes on posts I can no longer see.

CONTRACT (keep this docstring; implement exactly this):
Notation: db = request.db, me = request.me.id (write both as the function's first lines).
Hidden post: its author is neither me nor a friend of me (e.g. after an unfriend).
GET /api/activity/hidden                                                       (read-only)
  cs = db.all("SELECT c.id, c.post_id, c.body, c.created_at, p.author_id AS post_author_id"
              " FROM comments c JOIN posts p ON p.id = c.post_id"
              " WHERE c.author_id = ? AND p.author_id != ? AND p.author_id NOT IN"
              " (SELECT friend_id FROM friendships WHERE user_id = ?)"
              " ORDER BY c.id DESC LIMIT 100", me, me, me)
  ls = db.all("SELECT l.post_id, l.created_at, p.author_id AS post_author_id"
              " FROM likes l JOIN posts p ON p.id = l.post_id"
              " WHERE l.user_id = ? AND p.author_id != ? AND p.author_id NOT IN"
              " (SELECT friend_id FROM friendships WHERE user_id = ?)"
              " ORDER BY l.created_at DESC, l.post_id DESC LIMIT 100", me, me, me)
  -> 200 {"comments": [{"id": r["id"], "post_id": r["post_id"],
                        "post_author": user_json(require_user(db, r["post_author_id"])),
                        "body": r["body"], "created_at": r["created_at"]} for r in cs],
          "likes": [{"post_id": r["post_id"],
                     "post_author": user_json(require_user(db, r["post_author_id"])),
                     "created_at": r["created_at"]} for r in ls]}
Only my own comments and likes; never the post's body, its counts or other users' rows.
"""

from chatbook.core.api import HTTPError, Request, Response, route


@route("GET", "/api/activity/hidden")
def hidden_activity(request: Request) -> Response:
    raise HTTPError(501, "not implemented")
```
`src/chatbook/features/activity/__init__.py`:
`"""activity: my comments and likes on posts I can no longer see."""`

---

## D. The activity page (new feature `page_activity`, task cb-34)

| Setting | Value |
|---|---|
| Page name | `activity` (URL `#/activity`) |
| Title | `My activity` |
| Nav label and order | `Activity`, 45 (between Feed 40 and Profile 50) |
| Public | no |
| Poll | none |

- **Quoted texts:** `Your comments and likes on posts you can no longer see`,
  `Comments (n)`, `Likes (n)`, `You commented on a post by`, `You liked a post by`, `Delete`,
  `Unlike`, `No comments to remove`, `No likes to remove`.
- **Testids:** `delete-<comment id>`, `unlike-<post id>`.
- **After a click:** the DELETE, then `CB.refresh()`. No toast, no navigation. On an error answer
  `CB.api` shows a toast and stops, so no refresh follows.
- **Links:** `CB.userLink(post_author)` opens the author's profile (where "Add friend" would bring
  the post back). No link to the post: its page answers 404 now.
- **No confirm** (P2 item 12 should cover this page too).

**Stub `src/chatbook/features/page_activity/ui.js`** (block: 24 lines, longest line 97):
```js
// page_activity: my comments and likes on posts I can no longer see.
// CONTRACT (keep this comment; implement exactly this):
// CB.page('activity', {title: 'My activity', nav: 'Activity', order: 45, load, render})  no poll
// load(): return await CB.api('GET', '/api/activity/hidden')
// render(d) -> CB.el('div', {class: 'stack'}, in this order:
//   CB.el('p', {class: 'muted'}, 'Your comments and likes on posts you can no longer see'),
//   CB.el('h2', {}, 'Comments (' + d.comments.length + ')'),
//   d.comments.length ? d.comments.map((k) => CB.el('div', {class: 'item'},
//       CB.el('span', {}, 'You commented on a post by'), CB.userLink(k.post_author),
//       CB.el('span', {}, k.body), CB.el('small', {class: 'muted'}, CB.time(k.created_at)),
//       CB.el('button', {testid: 'delete-' + k.id, onclick: async () => {
//           await CB.api('DELETE', '/api/comments/' + k.id); CB.refresh(); }}, 'Delete')))
//     : CB.el('p', {class: 'muted'}, 'No comments to remove'),
//   CB.el('h2', {}, 'Likes (' + d.likes.length + ')'),
//   d.likes.length ? d.likes.map((l) => CB.el('div', {class: 'item'},
//       CB.el('span', {}, 'You liked a post by'), CB.userLink(l.post_author),
//       CB.el('small', {class: 'muted'}, CB.time(l.created_at)),
//       CB.el('button', {testid: 'unlike-' + l.post_id, onclick: async () => {
//           await CB.api('DELETE', '/api/posts/' + l.post_id + '/like'); CB.refresh(); }},
//         'Unlike')))
//     : CB.el('p', {class: 'muted'}, 'No likes to remove'))
// Server answer: {comments: [{id, post_id, post_author: U, body, created_at}],
//   likes: [{post_id, post_author: U, created_at}]}   (a like has no id: use l.post_id)
// No link to the post (its page answers 404 now). No toast, no try/catch.

CB.page('activity', {
  title: 'My activity',
  nav: 'Activity',
  order: 45,
  render: () => CB.el('p', {class: 'muted'}, 'Coming soon'),
});
```
`src/chatbook/features/page_activity/__init__.py`:
`"""page_activity: my comments and likes on posts I can no longer see."""`

Trial run of the reference page (`run_page`): no errors, no unmatched calls; text order as
specified; clicking `delete-27` gives `[GET, DELETE /api/comments/27, GET]` with `nav == []` and
no toast; a 404 on Unlike gives one toast and no reload; clicking the author's name gives
`nav == [["profile", {"id": "5"}]]`; the page entry is
`{name: 'activity', title: 'My activity', nav: 'Activity', order: 45, public: False,
file: 'page_activity'}`.

---

## E. Reopening in place, and the staff frame commit

### E.1 Why in place, and the fallback

- **Base:** the gates stay green (only docstrings change, plus the regenerated snapshot). The new
  tests fail on the old code, so `check_baseline` accepts the task (it only needs the hidden
  suite to be not ok). Checked.
- **`main` keeps working** the whole time. Its two CONTRACT blocks are just ahead of the code
  until the wave merges.
- **Worker fit:** a 4-6 line change in a 60-95 line file the model wrote itself. Retries are
  already in-place edits, and all 6 earlier retried tasks passed.
- **Provenance:** staff touch only the docstrings (frame-owned). Every code line stays
  model-written.
- **Integrate:** the new branch is an ordinary diff from the new `main`.

**Fallback ladder** (DESIGN 8.1) if an in-place task fails 4/4:
1. Rerun once unchanged.
2. `-e local-14b`: its single pass sees the prompt, which quotes the current and the new body
   (Decision 19). An iteration line `no changes` means the architect thought the code already
   matched: treat it as a prompt problem, not sampling noise, so never rerun more than once
   before this step.
3. Re-spec (prompt and CONTRACT), re-validate on the oracle, rerun.
4. A staff commit that resets that one file to its new CONTRACT stub (the carried suite still
   fails on base, so the baseline holds), and rerun.
5. If that fails too, give the feature its old state back in one staff commit:
   `git -C chatbook checkout <P1 frame commit>^ -- src/chatbook/features/<likes|comments>/handler.py`,
   then `py tools/check_extra.py --write-contracts` (1 changed). This restores the old CONTRACT
   and the model's cb-24/cb-25 code byte for byte, and undoes a stub reset too, so provenance
   stays intact. Do not `git revert` the frame commit: it also holds `can_see_post`, the
   activity stubs and the other feature's block. The old branch (cb-24 or cb-25) was never
   retired (retirement happens only at G.4 step 11), so it stays on `accepted.txt` and its
   suite keeps running. Hold back cb-34 (merge rule 17).

cb-33 (a stub task) follows the usual DESIGN 8.1 ladder. If it is abandoned, hold back cb-34 too
(merge rule 17); the activity stub stays ("Coming soon") or is dropped (DESIGN 8.1 step 6).

### E.2 The staff frame commit on chatbook `main`

One commit, message `P1 frame: can_see_post, own like/comment removable after unfriend, one
404, activity stubs`. Exactly these files:

1. **`src/chatbook/core/social.py`**: append (below `visible_post`, which does not change):
   ```python


   def can_see_post(db: Db, post_id: int, viewer_id: int) -> bool:
       """True if the post exists and its author is the viewer or a friend of the viewer."""
       row = db.one("SELECT author_id FROM posts WHERE id = ?", post_id)
       if row is None:
           return False
       author = int(row["author_id"])
       return author == viewer_id or are_friends(db, viewer_id, author)
   ```
2. **`src/chatbook/core/api.py`**: add `can_see_post,` to the `from chatbook.core.social import`
   list (after `befriend,`), and `"can_see_post",` to `__all__` right after `"visible_post",`.
3. **`tests/test_api_doc.py`**: add `"can_see_post",` to `ALL` right after `"visible_post",`.
   (`test_the_public_contract_is_exact` asserts `api.__all__ == ALL`. Drafts P and H missed this.)
4. **`docs/api/posts.md`**: under `## Helper`, after the two `visible_post` lines, add:
   ```
   can_see_post(db, post_id, viewer_id) -> bool
       True if the post exists and its author is the viewer or a friend of the viewer;
       never raises. A post is hidden from me when this is False (e.g. after an unfriend)
   ```
5. **`tests/test_social.py`**: add `can_see_post,` to the `from chatbook.core.social import`
   list (after `befriend,`) and append:
   ```python


   def test_can_see_post() -> None:
       db, (a, b, c, d) = make_db()
       befriend(db, a, b, NOW)
       befriend(db, b, c, NOW)
       befriend(db, a, d, NOW)
       pid = db.run("INSERT INTO posts (author_id, body, created_at) VALUES (?, ?, ?)", a, "hi", NOW)
       unfriend(db, a, d)
       cases = [(pid, a, True), (pid, b, True), (pid, c, False), (pid, d, False), (999, a, False)]
       for post_id, viewer, seen in cases:
           assert can_see_post(db, post_id, viewer) is seen
           if seen:
               assert visible_post(db, post_id, viewer)["id"] == post_id
           else:
               with pytest.raises(HTTPError) as info:
                   visible_post(db, post_id, viewer)
               assert (info.value.status, info.value.message) == (404, "post not found")
       befriend(db, a, d, NOW)
       assert can_see_post(db, pid, d) is True
   ```
   (self, friend, friend of a friend, ex-friend, missing id, friends again; it also pins
   `visible_post`'s exact 404.)
6. **`tests/test_route_map.py`**: add to `ROUTES` (after the suggestions row)
   `("GET", "/api/activity/hidden", False, "activity"),` and to `PAGES` (after the feed row)
   `("activity", "Activity", 45, False, "page_activity"),`. `UI_FEATURES` follows from `PAGES`.
7. **`src/chatbook/features/likes/handler.py`**: replace only the docstring (24 lines). The
   imports and the code stay as they are. The Notation line gains a coding hint (Decision 19;
   99 characters).
   ```
   """likes: like, unlike and list likers.

   CONTRACT (keep this docstring; implement exactly this):
   Notation: db = request.db, me = request.me.id (the code below writes request.db and request.me.id).
   n = int(db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid)) after the change
   POST /api/posts/{id}/like
     pid = path_id(request); visible_post(db, pid, me)                  (404)
     db.run("INSERT OR IGNORE INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
            pid, me, request.now)
     -> 200 {"post_id": pid, "like_count": n, "liked": True}
   DELETE /api/posts/{id}/like   (me may remove its own like even from a post me can't see)
     pid = path_id(request)                                             (404)
     gone = db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, me)
     if not can_see_post(db, pid, me):      (post missing, or author neither me nor a friend)
       gone == 0 -> raise HTTPError(404, "post not found")    (exactly the 404 of visible_post)
       -> 200 {"post_id": pid, "liked": False}                (no like_count: a hidden post)
     -> 200 {"post_id": pid, "like_count": n, "liked": False}
   GET /api/posts/{id}/likes
     pid = path_id(request); visible_post(db, pid, me)                  (404)
     rows = db.all("SELECT u.* FROM likes l JOIN users u ON u.id = l.user_id"
                   " WHERE l.post_id = ? ORDER BY l.created_at, u.id", pid)
     -> 200 {"users": [user_json(r) for r in rows]}
   Tables you may write: likes.
   """
   ```
8. **`src/chatbook/features/comments/handler.py`**: in the docstring, replace the Notation line
   and the DELETE part (from `DELETE /api/comments/{id}` to the closing `"""`). The block grows
   from 25 to 26 lines. The K, GET and POST lines and all code stay as they are. The Notation
   line becomes the same line as in item 7:
   ```
   Notation: db = request.db, me = request.me.id (the code below writes request.db and request.me.id).
   ```
   The DELETE part:
   ```
   DELETE /api/comments/{id}   (me may delete its own comment even on a post me can't see)
     cid = path_id(request); row = db.one("SELECT * FROM comments WHERE id = ?", cid)
     row is None -> raise HTTPError(404, "post not found")    (exactly the 404 of visible_post)
     if row["author_id"] != me:
       post = visible_post(db, row["post_id"], me)                      (404)
       post["author_id"] != me -> 403
     DELETE FROM comments WHERE id = ?  -> 200 {"deleted": cid}
   Tables you may write: comments.
   """
   ```
9. **New `src/chatbook/features/activity/__init__.py` and `handler.py`**: the stub in C.
10. **New `src/chatbook/features/page_activity/__init__.py` and `ui.js`**: the stub in D.
11. **`tools/contracts.json`**: run `py tools/check_extra.py --write-contracts`. The output must be
    exactly: `32 CONTRACT block(s)`; added `activity/handler.py`, `page_activity/ui.js`;
    changed `comments/handler.py`, `likes/handler.py`; **no REMOVED**.
12. **`AGENTS.md`**: under `## Your file`, after the bullet "The file must still begin with its
    CONTRACT block, unchanged; your code goes below it.", add:
    ```
    - Some tasks change a feature that already works: the file then holds working code below a
      changed CONTRACT block. Change only what the task names, so the code matches the CONTRACT
      again; keep everything else exactly as it is.
    ```

**Not changed:** `cb.js`, `cb.css`, `docs/ui.md`, `docs/api/base.md`, the schema, the demo seed,
`swarm.toml`.

**Gates before committing** (HANDOFF section 4): `ruff check`, `ruff format --check`, `mypy src`,
`pytest tests` (now **291**), `check_extra.py`, and `swarm -t chatbook archlint`. The first five
passed in the scratch trial, before the Notation lines of items 7-8 changed (run them again);
archlint was not run (the stubs import only `chatbook.core.api`).

### E.3 Docs outside the product repo (root repo commit)

- **DESIGN.md:**
  - section 0: row 22 "reopen a finished feature in place (staff change the CONTRACT, the model
    edits its code); stub reset is the fallback"; row 23 "a reopened task supersedes its old
    branch; regression list = `harness/accepted.txt`";
  - 1.2 / 1.3: the "My activity" feature and the page-map row
    `activity | My activity | Activity (45) | nav | page_activity`;
  - 3.1: the error-text exception (B), and two spec shapes: AC = `{"id", "post_id",
    "post_author": U, "body", "created_at"}`, AL = `{"post_id", "post_author": U, "created_at"}`;
  - 3.5 and 3.10: `can_see_post`;
  - 3.17: the route row, stub names `activity hidden_activity`, and the page via 1.3;
  - 3.18: the posts.md lines; 3.19: `test_can_see_post`, 291 frame tests;
  - 5: the AGENTS.md bullet;
  - 6.5: a new "Polish P1" section with the four specs (the blocks above plus the prompt notes in
    G), and a note on cb-24/cb-25: "superseded by cb-31/cb-32";
  - 7.2 step 4: integrate from `harness/accepted.txt`, not from `git branch --list`; a wave that
    reopens a feature leaves out only the old branches whose replacement passed, and retires
    them after the merge (G.4 steps 9 and 11);
  - 6.5 / 7: merge rule 17 (cb-34 only with cb-31, cb-32 and cb-33);
  - 7.3: the P1 smoke steps (G.5); 8.1 step 4: the in-place reopen and its fallback.
- **HANDOFF.md:** 6.2(a): replace "A re-opened task needs its stub put back on the base ..." with
  the in-place rule; step 6 becomes "integrate with every branch in `harness/accepted.txt`; once
  the new branch is accepted it replaces its old one, which moves to the retired block". 2a and
  6.3 step 4: same list. Section 1 state and section 4 health check: 291 frame tests. 6.0 step 3:
  "an integrate needs the branches listed in `harness/accepted.txt` as local branches" (not "the
  30 accepted"); the fetch of `refs/heads/agent/*` there also brings the retired branches, which
  stay as records (they are ancestors of `main`). 6.0 step 4: 291 frame tests.
- **notes/polish-backlog.md:** items 10 and 11 -> "in P1 (cb-31..cb-34)".
- **PROGRESS.md:** the P1 entry.

---

## F. The old hidden tests

### F.1 Exactly what conflicts

Checked by running all 30 old suites against the reference: 935 pass, 2 fail.
- `cb-24-likes/acceptance/test_cb24_likes.py`, lines 262-270:
  `test_former_friend_gets_404_and_keeps_old_like[DELETE-like]`. Tara's own like on the
  ex-friend's post now gives 200 and is removed.
- `cb-25-comments/acceptance/test_cb25_comments.py`, lines 349-366:
  `test_delete_when_the_post_is_hidden_is_404[unfriended_author]`. Rosa's own comment after the
  unfriend now gives 200.

The brief also pointed at cb-25 lines 120-140 and 250-270. Those are GET and POST on a hidden
post. They still answer 404, so they **do not** conflict. `test_former_friends_like_still_counts`
(cb-24) does not conflict either.

### F.2 Resolution: supersede (the old task folders are not touched)

- **cb-31** carries `test_cb24_likes.py` as `acceptance/test_cb31_from_cb24.py`. Changes:
  - a header comment: `# Carried from cb-24-likes (harness 2ecb8e5). Changed per owner decision
    2026-10-28 (backlog 10a, 11): a former friend may now remove an own like; see
    test_cb31_likes.py.`;
  - `test_former_friend_gets_404_and_keeps_old_like` becomes
    `test_former_friend_cannot_like_or_list`, parametrized over
    `[("POST", "like"), ("GET", "likes")]` with `ids=["post", "get"]`. Its body stays.
  - Everything else is verbatim.
- **cb-32** carries `test_cb25_comments.py` as `acceptance/test_cb32_from_cb25.py`, with the same
  kind of header comment. In `test_delete_when_the_post_is_hidden_is_404`, the case
  `unfriended_author` becomes `unfriended_other`: the setup adds
  `by_tia = c.comment(tia, sams, "nice view")`; after `c.unfriend(rosa, sam)` rosa tries to
  delete `by_tia` -> 404, nothing deleted. The unfriend path stays tested for other users'
  comments. Add `ids=` to that parametrize.
- **`cb-24-likes/` and `cb-25-comments/` stay byte for byte.** Each still matches its own accepted
  branch as a record.
- **New file `harness/accepted.txt`** (the regression list), committed at G.4 step 4 with all 30
  branches active:
  ```
  # ChatBook regression list: accepted worker branches, one per line (# = comment).
  # Integrate every wave with all of these plus the wave's new branches (PowerShell):
  #   $keep = Get-Content E:/Playground_Projects/05_ChatBook/harness/accepted.txt |
  #           Where-Object { $_ -and -not $_.StartsWith('#') }
  #   <swarm> -t chatbook integrate $keep <new branches>
  # A wave that reopens a feature leaves out only the old branches whose replacement passed.
  # Once the replacement is accepted, the old branch moves to the retired block below; the new
  # task carries its suite. Never list a retired branch: its old suite contradicts the new rules.
  agent/cb-01-accounts--local-14b-arch--20261027-173512-a3bd
  agent/cb-02-people--local-14b-arch--20261027-173853-c4d0
  agent/cb-03-friend_requests--local-14b-arch--20261027-174201-06fa
  agent/cb-04-friend_answers--local-14b-arch--20261027-174643-e1e5
  agent/cb-05-friends--local-14b-arch--20261027-184618-e210
  agent/cb-06-page_login--local-14b-arch--20261027-175413-9596
  agent/cb-07-dm--local-14b-arch--20261027-192455-49fa
  agent/cb-08-groups--local-14b-arch--20261027-192931-35be
  agent/cb-09-group_members--local-14b-arch--20261027-193434-e448
  agent/cb-10-conversations--local-14b-arch--20261027-195013-b76c
  agent/cb-11-chat_send--local-14b-arch--20261027-195343-49ee
  agent/cb-12-chat_history--local-14b-arch--20261027-195902-7e2a
  agent/cb-13-updates--local-14b-arch--20261027-200248-135d
  agent/cb-14-profiles--local-14b-arch--20261027-200510-0e6d
  agent/cb-15-page_people--local-14b-arch--20261027-201031-086e
  agent/cb-16-page_friends--local-14b-arch--20261027-202521-d29b
  agent/cb-17-page_inbox--local-14b-arch--20261027-204504-876b
  agent/cb-18-page_chat--local-14b-arch--20261027-205615-565b
  agent/cb-19-page_group_new--local-14b-arch--20261027-210518-b518
  agent/cb-20-page_group--local-14b-arch--20261027-210816-a745
  agent/cb-21-page_profile--local-14b-arch--20261027-211301-3fd4
  agent/cb-22-badges--local-14b-arch--20261027-211746-5878
  agent/cb-23-posts--local-14b-arch--20261028-012459-5205
  agent/cb-24-likes--local-14b-arch--20261028-014937-36e3
  agent/cb-25-comments--local-14b-arch--20261028-015647-cfda
  agent/cb-26-presence--local-14b-arch--20261028-020117-c2b5
  agent/cb-27-suggestions--local-14b-arch--20261028-020402-59e4
  agent/cb-28-page_feed--local-14b-arch--20261028-020737-5136
  agent/cb-29-page_post--local-14b-arch--20261028-022141-0d74
  agent/cb-30-page_discover--local-14b-arch--20261028-022831-703c
  # retired:
  ```
  At G.4 step 11 (after the merge to `main`), each accepted P1 branch is added, and only the old
  branch it replaces moves to the retired block, e.g.
  `# agent/cb-24-likes--local-14b-arch--20261028-014937-36e3     superseded by cb-31-likes` and
  `# agent/cb-25-comments--local-14b-arch--20261028-015647-cfda  superseded by cb-32-comments`.
  If cb-31 or cb-32 is abandoned (E.1 step 5), its old branch stays active. The old branches stay
  in git (they are ancestors of `main`); a retired one is only left out of the list.
- **Why this is safe:** `dispatch.integrate` runs the hidden suite of every branch it merges,
  looked up by task id, and only of those. A retired branch listed by mistake fails integrate on
  exactly the 2 known cases (loud). A branch left out by mistake is silent, which is why an old
  branch leaves the list only when its replacement (whose suite carries the old one) is merged.
  A missing or mistyped name is only logged as "ignored", so always check the line
  `integration OK: N branch(es) merged`: N = 30 + the P1 branches merged - the old branches left
  out; 32 when all 4 pass.
- **Fallback (owner question 1):** keep both old branches on the list and edit only those 2
  parametrize lists in the old suites, each with a comment that it is an owner-decided spec change
  (backlog 10a), not a change to make a worker pass. The carried files then stay as above.

### F.3 The new hidden tests

All suites: explicit short `ids=` on every parametrize, no long parameter values, fixture names and
values different from the prompt examples, one error condition per request, and the import test
last.

**cb-31-likes** (`test_cb31_from_cb24.py` as in F.2, plus `test_cb31_likes.py`):
1. An ex-friend removes an own like while 2 other likes exist on that post: exactly
   `(200, {"post_id": pid, "liked": False})` (a leaked count would show). Only that row is gone;
   my like on another hidden post stays.
2. The unfriend may come from either side (`ids=["i_unfriend", "they_unfriend"]`).
3. A never-friend's seeded like (`c.like` on a stranger's post): 200, same shape.
4. A second removal: 404, and its `(status, json)` equals both `DELETE /api/posts/9999/like` and
   `POST /api/posts/9999/like` (a body made by `visible_post`; DELETE against DELETE alone would
   pass any text, see B); nothing changes.
5. Hidden post without my like (stranger, friend of a friend, ex-friend who never liked): 404,
   `(status, json)` equal to `GET /api/posts/<that post>/likes` (also `visible_post`'s) and to
   `DELETE /api/posts/9999/like`; no rows change.
6. After the removal, POST and GET on that post still answer 404, bodies equal to a missing post.
   (Tests 4-5 kill the mutant "another 404 text" in `unlike_post`; test 6 alone cannot.)
7. Friends again: the visible path, 200 with the real `like_count`.
8. A post deleted the normal way (post row and its likes removed with `c.db.run`): 404.
9. The author unlikes their own post with no friends: 200 with `like_count`.
10. The module imports.

**cb-32-comments** (`test_cb32_from_cb25.py` as in F.2, plus `test_cb32_comments.py`):
1. An ex-friend deletes an own comment: `(200, {"deleted": cid})`; the other comments stay.
2. Either side unfriends.
3. A never-friend's seeded own comment on a stranger's post: 200.
4. An ex-friend deleting someone else's comment on the hidden post: 404 (not 403), nothing changes.
5. **Item 11:** for the actors stranger, friend of a friend and ex-friend: the hidden comment id,
   `999` and an already-deleted id all give 404 with **equal** `json` bodies, and they equal the
   body of `GET /api/posts/<hidden>/comments` by the same actor (made by `visible_post`). Without
   that comparison a wrong text such as "comment not found" passes (found by the cb-32 review).
6. My own hidden comment deleted twice: the second body equals the missing-id body.
7. Friends again: someone else's comment on that post gives 403 again.
8. The post's author still deletes an ex-friend's comment on their own post: 200.
9. The module imports.

**cb-33-activity** (`test_cb33_activity.py`; cast: kai = me, lena = friend, mo and nia =
ex-friends, omar = never a friend, pia = a friend of mo only, plus my own post):
1. Exact JSON for a mixed scenario: only mo's and nia's posts listed; my own post, lena's post
   and other users' rows excluded.
2. The post body text never appears in `r.text`; each item's key set is exact (no `body` of the
   post, no counts).
3. Comments come in `id DESC` even after `created_at` is rewritten with `c.db.run` so that a
   `created_at` order would fail.
4. Likes come in `created_at DESC`, with a tie broken by `post_id DESC`.
5. Both unfriend directions.
6. Activity made while friends appears after the unfriend; friends again -> it disappears.
7. `post_author` follows a `display_name` change (`c.db.run UPDATE users`).
8. Cap: 101 comments and 102 likes give 100 each (check the length and the first and last ids).
9. Empty: `{"comments": [], "likes": []}`.
10. Read-only: the tables are the same after the request. Snapshot `posts`, `likes`, `comments`,
    `friendships`, `friend_requests`, `sessions`, every `users` column except `last_seen_at`, and
    the full rows of the other users (copy the query of cb-26 `test_listing_writes_nothing`).
    The App itself sets the viewer's `last_seen_at` on every logged-in request (`touch` in
    `app.py`), so "every table unchanged" would fail on the reference.
11. Orphan rows (the post row deleted with `c.db.run`, its likes and comments kept) are not
    listed.
12. 401 without login.
13. The module imports.

**cb-34-page_activity** (`test_cb34_page_activity.py`; fixtures: comments 31 and 27 on posts by
ERIN and FRANK, one body with `<b>`; likes on posts 9 and 6; every test asserts
`errors == []` and `unmatched == []`):
1. Registration exact (`order` 45, `nav` 'Activity', `public` False).
2. Exactly one `GET /api/activity/hidden`; `nav == []`; `toasts == []`.
3. Text order with `text.index`: intro, `Comments (2)`, the comment rows, `Likes (2)`, the like
   rows. Row texts as substrings; `CB.time` text is not asserted.
4. Labels exactly `["Delete", "Delete", "Unlike", "Unlike"]`; testids `delete-31`, `delete-27`,
   `unlike-9`, `unlike-6`.
5. `click_id delete-27` -> calls `[GET, ["DELETE", "/api/comments/27", None], GET]`, no nav, no
   toast.
6. `click_id unlike-6` -> `DELETE /api/posts/6/like`, then GET.
7. A DELETE answered `{"$status": 404, ...}` -> one toast, one GET only.
8. Both lists empty -> `Comments (0)`, `No comments to remove`, `Likes (0)`,
   `No likes to remove`, no buttons.
9. Only comments; only likes.
10. Clicking an author's name -> `nav == [["profile", {"id": "5"}]]`.
11. `tick 60000` -> still one GET (no poll).
12. HTML in a comment body is shown as text.
13. `"activity"` is in `run_page("page_activity", None).pages` names.

Each suite must fail on the new `main` (in-place tasks: the new tests; stubs: 501 / "Coming
soon") and pass with its `solution.patch`.

---

## G. Task list, prompts and run order

| Id | Title | Kind / `type` | Files (editable first, then read-only) | Scope | Expected result |
|---|---|---|---|---|---|
| cb-31-likes | Likes: remove your own like from a post you can no longer see | backend, in place / `fix` | `src/chatbook/features/likes/handler.py`, `docs/api/base.md`, `docs/api/posts.md` | `src/chatbook/features/likes/**` | `unlike_post` +5/-2 lines, import gains 2 names; file about 75 lines (ruff wraps the import) |
| cb-32-comments | Comments: delete your own comment on a hidden post; one 404 for hidden and missing | backend, in place / `fix` | `.../comments/handler.py`, base.md, posts.md | `.../comments/**` | `delete_comment` +5/-4; no new import; file about 96 lines |
| cb-33-activity | Activity: your comments and likes on posts you can no longer see | backend, stub / `feat` | `.../activity/handler.py`, base.md, posts.md | `.../activity/**` | measured reference: 75 lines |
| cb-34-page_activity | My activity page | UI, stub / `feat` | `.../page_activity/ui.js`, `docs/ui.md` | `.../page_activity/**` | measured reference: 50 lines |

The ids are unique by prefix (`cb-31` .. `cb-34`), and `cb-24` / `cb-25` stay unique.

### G.1 The cb-31 prompt (about 530 words counting the code lines, ASCII)

The current body is quoted as "wrong now" and the new body in full (Decision 19): an attempt that
changes nothing gets no test output, so the prompt alone must show that the file has to change.

```
The feature `likes` in `src/chatbook/features/likes/handler.py` already works. Its CONTRACT
docstring was changed for one route only: DELETE /api/posts/{id}/like (function
`unlike_post`). The code of `unlike_post` does not match the new CONTRACT yet, so this task
always changes the file. Change only the function `unlike_post` and the import line. Keep the
CONTRACT docstring, the three @route lines, the function names and the functions `like_post`
and `list_likes` exactly as they are.
Reference: docs/api/base.md and docs/api/posts.md (read-only).
Notation: db = request.db, me = request.me.id. In code write request.db and request.me.id,
as the rest of the file does.

Why: after an unfriend, a user must still be able to remove their own like from the former
friend's post, but must learn nothing else about that post.

Current body of unlike_post (wrong now: it calls visible_post first, so a post me cannot see
always gives 404, even when me has a like on it):
    pid = path_id(request)
    visible_post(request.db, pid, request.me.id)
    request.db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, request.me.id)
    n = int(request.db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid))
    return Response(200, {"post_id": pid, "like_count": n, "liked": False})

New body of unlike_post (replace the whole body with these lines, in this order):
    pid = path_id(request)
    gone = request.db.run("DELETE FROM likes WHERE post_id = ? AND user_id = ?", pid, request.me.id)
    if not can_see_post(request.db, pid, request.me.id):
        if gone == 0:
            raise HTTPError(404, "post not found")
        return Response(200, {"post_id": pid, "liked": False})
    n = int(request.db.value("SELECT COUNT(*) FROM likes WHERE post_id = ?", pid))
    return Response(200, {"post_id": pid, "like_count": n, "liked": False})
db.run returns the number of rows deleted (0 or 1). A bad id makes path_id raise 404 itself.

Imports: add HTTPError and can_see_post to the existing import from chatbook.core.api. Keep
visible_post: like_post and list_likes still use it.

Details:
- can_see_post(db, post_id, viewer_id) -> bool is a frame helper (docs/api/posts.md). It is
  False when the post does not exist or its author is neither me nor a friend of me. It never
  raises.
- When me cannot see the post, the 200 answer has exactly the keys "post_id" and "liked". No
  "like_count": me may not learn how many likes the post has.
- When me cannot see the post and had no like on it, the answer must be exactly the 404 that
  visible_post gives: HTTPError(404, "post not found"). Hidden tests compare it with the 404
  that POST and GET give for a post that does not exist or that me cannot see.
- When me can see the post, nothing changes: 200 with like_count, also when me had no like.
- POST and GET do not change: they still answer 404 for a post me cannot see.

Example: ann (id 3) and bo (id 4) were friends; bo wrote post 11; ann liked it; then they
unfriended. As ann, DELETE /api/posts/11/like -> 200 {"post_id": 11, "liked": false}, and
ann's like is gone. The same request again -> 404 {"error": "post not found"}, the same answer
as DELETE or POST /api/posts/888/like when post 888 does not exist.

JSON keys, status codes and list order must match exactly. Error texts are not tested, except
this one: the 404 answers above must be exactly HTTPError(404, "post not found").
```

### G.2 The cb-32 prompt (same pattern, about 500 words)

- Opening: "The feature `comments` ... already works. Its CONTRACT docstring was changed for one
  route only: DELETE /api/comments/{id} (function `delete_comment`). The code of
  `delete_comment` does not match the new CONTRACT yet, so this task always changes the file.
  Change only `delete_comment`. Keep the docstring, the @route lines, the function names and
  `comment_json`, `list_comments`, `add_comment` exactly as they are." Same Notation line.
- Why: (1) after an unfriend a user must still be able to delete their own comment on the former
  friend's post; (2) a missing comment and a comment on a post me cannot see must give the same
  404, so nobody can find out which hidden comment ids exist.
- "Current body of delete_comment (wrong now: it says "comment not found", and it calls
  visible_post for every comment, so me's own comment on a post me cannot see gives 404)",
  quoting the 9 current lines exactly as they are on `main`:
  ```
      cid = path_id(request)
      row = request.db.one("SELECT * FROM comments WHERE id = ?", cid)
      if row is None:
          raise HTTPError(404, "comment not found")
      post = visible_post(request.db, row["post_id"], request.me.id)
      if request.me.id != row["author_id"] and request.me.id != post["author_id"]:
          raise HTTPError(403, "forbidden")
      request.db.run("DELETE FROM comments WHERE id = ?", cid)
      return Response(200, {"deleted": cid})
  ```
- "New body of delete_comment (replace the whole body with these lines, in this order)":
  ```
      cid = path_id(request)
      row = request.db.one("SELECT * FROM comments WHERE id = ?", cid)
      if row is None:
          raise HTTPError(404, "post not found")
      if row["author_id"] != request.me.id:
          post = visible_post(request.db, row["post_id"], request.me.id)
          if post["author_id"] != request.me.id:
              raise HTTPError(403, "forbidden")
      request.db.run("DELETE FROM comments WHERE id = ?", cid)
      return Response(200, {"deleted": cid})
  ```
- "No new imports are needed."
- Details: me's own comment is deleted even when me cannot see the post; for someone else's
  comment the old rules stay (404 when hidden, 403 when me wrote neither the comment nor the
  post; the post's author may delete any comment on their post); GET and POST do not change.
- Example with fresh names (not rosa/sam/tia/ugo/vik), and the same closing line as cb-31.

### G.3 The cb-33 and cb-34 prompts

- **cb-33** follows cb-27: "Implement the feature `activity` ... The file is a stub: keep its
  CONTRACT docstring, its @route line and the function name `hidden_activity`, and replace the
  `raise HTTPError(501, ...)`." Then the CONTRACT text verbatim, and these lines:
  - "Start the function with `db = request.db` and `me = request.me.id`."
  - "Copy both SQL texts exactly as shown, as adjacent string literals (never + or f-strings),
    with the parameters `me, me, me`."
  - "Import require_user and user_json from chatbook.core.api. HTTPError is not needed: remove it
    from the import (an unused import fails the lint gate). If you annotate a dict, use
    `dict[str, Any]` with Any from typing."
  - Details: what "hidden" means; the order and the 100 limit; `post_author` is the post's author,
    not me; `body` and `created_at` are my comment's; never the post's body or counts.
  - An example with fresh names.
- **cb-34** follows cb-30: keep the block and `CB.page('activity', ...)` with title, nav and order;
  replace `render` with `load` and `render`; one blank line after the block. Then the CONTRACT
  verbatim, and: "no `poll`, no `CB.avatar`, no `try`/`catch`, no toast, no request other than the
  3 listed, no link to the post; a like has no id, use `l.post_id`". An example with fresh names,
  and the usual closing line ("Texts, headings, classes, testids, button labels, request
  paths/bodies and element order must match exactly; error message texts are not tested.").

### G.4 Run order (runbook)

1. The owner answers the open questions below (done 2026-10-28).
2. Root repo docs commit (E.3).
3. chatbook frame commit (E.2) on `main`; run the gates and archlint.
4. Harness commit: the 4 task folders (each `solution.patch` made in a scratch worktree of the
   **new** `main` with `git diff --output=<abs>/solution.patch main -- src/chatbook/features/<name>`)
   and `harness/accepted.txt` with all 30 branches active (F.2; nothing retired yet). The old
   task folders are not touched.
5. Oracle:
   - `git -C chatbook-oracle pull --ff-only`; `swarm -t chatbook-oracle clean --branches`;
   - `swarm -t chatbook-oracle validate cb-31 cb-32 cb-33 cb-34 -j 2`;
   - `swarm -t chatbook-oracle integrate` (only the 4 oracle branches exist there). A successful
     integrate deletes its worktree; only the branch `integration/<stamp>` stays;
   - `git -C chatbook-oracle checkout integration/<stamp>` (as in DESIGN 7.1 step 8). By hand,
     against that tree (`PYTHONPATH=E:/Playground_Projects/05_ChatBook/chatbook-oracle/src`,
     `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, nothing copied into a repo): run all
     30 old suites. Expected: exactly the 2 cases of F.1 fail, everything else passes;
   - adversarial mutant review (each mutant in a scratch copy, never in a repo): old code; a
     leaked count; 200 when `gone == 0`; another 404 text (killed by cb-31 tests 4-5 and cb-32
     test 5, both through a comparison with a body made by `visible_post`); `visible_post` still first in cb-32; "comment not found" left in place; anyone
     deleting comments on hidden posts; activity listing visible or own posts or other users'
     rows; wrong order; no LIMIT; a post-body leak; a page using `CB.go` instead of refresh, a
     toast, a poll, or `l.id`;
   - `git -C chatbook-oracle checkout main`; `swarm -t chatbook-oracle clean --branches`.
6. Start Ollama on the GPU (HANDOFF 6.1) and check `size_vram`.
7. `swarm -t chatbook run cb-31 -j 1`. Read its diff, iterations and token counts (architect
   input target < 5.5k). An iteration line `no changes` is a prompt problem (E.1 step 2).
8. `swarm -t chatbook run cb-32 cb-33 cb-34 -j 1` (log to `harness/runs/p1.log`). About 30-45 min
   for the wave. A failed task goes through E.1 before step 9; an abandoned in-place task has
   its old file restored on `main` first (E.1 step 5).
9. Integrate. `$keep` from `accepted.txt`, minus only the old branch whose replacement passed,
   plus the passing P1 branches (PowerShell):
   ```
   $keep = Get-Content E:/Playground_Projects/05_ChatBook/harness/accepted.txt |
           Where-Object { $_ -and -not $_.StartsWith('#') }
   $keep = $keep | Where-Object { $_ -notlike 'agent/cb-24-likes--*' }      # only if cb-31 passed
   $keep = $keep | Where-Object { $_ -notlike 'agent/cb-25-comments--*' }   # only if cb-32 passed
   <swarm> -t chatbook integrate $keep <passing P1 branches>
   ```
   If cb-31, cb-32 or cb-33 did not pass, leave cb-34 out (merge rule 17). Check
   `integration OK: N branch(es) merged` with N as in F.2 (32 when all 4 pass).
10. Provenance (`git -C chatbook log --format=%b main..integration/<stamp>`: one `local-14b-arch`
    commit per merged P1 branch, only their feature files), code review, browser smoke (G.5).
11. `git -C chatbook merge --ff-only integration/<stamp>`; `swarm -t chatbook clean` (no
    `--branches`). In `accepted.txt`: add the merged P1 branches, and move cb-24 (only if cb-31
    merged) and cb-25 (only if cb-32 merged) to the retired block (F.2); harness commit. Update
    PROGRESS. Push only when the owner asks.

Never validate cb-31 .. cb-34 again after acceptance: their baseline then fails by design.

### G.5 Browser smoke for P1 (adds to DESIGN 7.3)

- alice and bob are friends. alice likes bob's post and comments on it. Then bob unfriends alice.
- alice: the Feed no longer shows bob's post. Activity shows `Comments (1)` and `Likes (1)` with
  bob's name and alice's comment, and no post text.
- Click bob's name: his profile opens.
- Delete, then Unlike: each row disappears; both empty texts show.
- bob: his post shows one like fewer and the comment gone.
- A feed tab alice opened before the unfriend: its Unlike now succeeds (no 404 toast).
- Stale post page (after the steps above): alice and bob are friends again; alice likes and
  comments on a second bob post and keeps its post page (`#/post/<id>`) open in a tab; bob
  unfriends alice. In that tab, Unlike, and Delete on her own comment, each succeed, then one
  "post not found" toast (the refresh gets 404) and the stale page stays (old count, the comment
  still shown); a second click toasts again. Expected P1 behaviour (H); Activity no longer lists
  what was removed.
- The top bar now has 7 entries: check it at 360 px width.

---

## H. Risks for the 14B worker (and others)

| Risk | What reduces it |
|---|---|
| In-place editing is new: the model rewrites other routes, or changes nothing ("already matches") | A no-op attempt gets **no** test output: the runner runs the gates and the hidden tests only when something changed, the feedback is one sentence ("No file changes remain. Edit the source files to complete the task."), and an empty diff never triggers the stuck warning, so a no-op can repeat for all 4 iterations. Therefore the prompt says the file always changes and quotes the current body as "wrong now" next to the new body (Decision 19); the AGENTS.md bullet reaches the editor; the carried suites catch damage to other routes; cb-31 runs alone first; an iteration line `no changes` is treated as a prompt problem: after one rerun go straight to `-e local-14b`, whose single pass sees the prompt, then re-spec, then stub reset (E.1) |
| The model keeps `"comment not found"` (habit text already in the file) | The CONTRACT and the prompt name the new text; the body-equality test shows both bodies in the feedback |
| `like_count` added from habit, or `None` | The CONTRACT gives the exact dict; the test compares exact JSON |
| `can_see_post` / `HTTPError` not imported | The prompt lists the imports; ruff F821 and mypy name the missing name; posts.md documents the helper |
| The model edits the CONTRACT to match its code | The gate prints the block; autofix restores a deleted block (cb-28 precedent) |
| cb-33 repeats cb-23's failures (undefined `db`/`me`, E501) | The block itself says "write both as the function's first lines"; SQL pieces are pre-split (measured: no line over 100 after format). cb-31/cb-32: their blocks' Notation line says the code writes `request.db` and `request.me.id`, and the prompts quote the new body in that form (Decision 19) |
| cb-33 uses `author_id` instead of the alias, or the wrong number of `me` | The alias and `me, me, me` are quoted; an sqlite error or exact-JSON diff shows in the feedback |
| cb-34 uses `l.id`, copies discover's `poll` or toast | The block says "a like has no id"; fixtures have no like id (`unlike-undefined` fails); no-poll and no-toast tests |
| Token budget: the comments file adds about 1k tokens over a stub, and the quoted current and new bodies add about 200-300 tokens to each in-place prompt | Expected architect input about 4.5-5.3k; measure on cb-31/cb-32. If over 5.5k, drop base.md from the in-place tasks |
| Feedback clipped at 3000 characters | Short `ids=`, short assertions, carried suites mostly pass so few failures print |
| The page merges without cb-31, cb-32 or cb-33 | Merge rule 17. Without cb-33 every visit shows a 501 toast and an error card; cb-34's mocked tests cannot see that, so the rule, not a test, holds it back |
| `main` between the frame commit and the merge | Shows an "Activity" nav entry with "Coming soon" (`/api/activity/hidden` answers 501), and two CONTRACT blocks ahead of their code. The product still works. If P1 fails for good: restore those 2 files from the frame commit's parent (E.1 step 5) and drop the activity stubs (DESIGN 8.1 step 6) |
| Integrate list mistakes | A listed retired branch fails loudly on the 2 known cases; a typo is only "ignored", so check the merged count. An old branch left out early would be silent (no likes or comments suite), so it leaves the list only at G.4 step 11, after its replacement merged |
| Stale post page after an unfriend (page_post is not reopened in P1) | Own Unlike or comment Delete now answers 200, then `CB.refresh()` reloads, `GET /api/posts/{id}` answers 404: one "post not found" toast, and the stale page stays (old like count, deleted comment still shown; cb.js keeps the shown page when a refresh fails). Another click toasts again. Known P1 behaviour, in the G.5 smoke; P2 note next to items 8 and 12 |
| Integrate on another PC | `integrate` reads `harness/runs/*/summary.json`, which is git-ignored, so old branches are "ignored" on a fresh clone and their suites do not run. Run P1 on this PC, or note it in HANDOFF 6.0 (this existed before P1) |
| Delete or Unlike on something already gone | Second request of a double click toasts "post not found" (also on page_post's comment Delete). On page_post, Delete on my own comment that the post's author deleted while the page was open also toasts "post not found" (was "comment not found"), which reads wrong although the post is visible. Known P1 behaviour (Decision 5); same class as backlog item 8 (P2 note) |

---

## Open questions for the owner (answered 2026-10-28)

1. **Old tests: supersede.** Integrate from `harness/accepted.txt`. Retire each old branch (cb-24,
   cb-25) from it only once its replacement (cb-31, cb-32) is accepted. The new tasks carry the
   old tests; the old task folders stay untouched. (Chief's call: a technical choice.)
2. **Where the page lives: a top-bar entry "Activity" (order 45) for everyone.** The page has no
   other way in. (Chief's call, reported to the owner; the owner may still ask for a profile link
   in P2.)
3. **What option (a) leaves open: accepted by the owner.** When choosing (a), the owner was told
   that a like or comment stays visible until you remove it.

The defaults below are kept. The stale post-page behaviour (P2 notes) is accepted for P1 and goes
to P2.

**Defaults taken (say if you want something else):** the hidden-post Unlike answer has no
`like_count`; a missing comment now answers "post not found"; each list shows at most the newest
100 items, with no paging, and its heading count counts the listed rows, so it shows at most 100
("Comments (100)" when you have more); comments are listed before likes; the page shows the
author's name and your own comment text, never the post's text; the texts in D.

**P2 notes:**
- Item 12 (confirm before delete) and item 8 (`CB.action`) should also cover the two buttons on
  this page.
- Next to items 8 and 12, for page_post (not reopened in P1): after an unfriend, a post page
  that was open before it lets you Unlike or Delete your own comment (200), but the refresh then
  toasts "post not found" and the stale page stays; Delete on your own comment that the post's
  author already deleted toasts "post not found". Item 8's "refresh after errors" plus a
  leave-the-page-on-404 rule would fix both.
