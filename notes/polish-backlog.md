# ChatBook: polish backlog (after the MVP)

These come from the code reviews of Waves 2 and 3 (workflows `wf_6ea4b958-858`, `wf_92667b9c-419`).
In every case the **local LLM implemented its CONTRACT exactly**. The gap is in the staff-written
spec, stub CONTRACT or frame. A worker who "fixed" them would have failed the CONTRACT gate or the
hidden tests.

**How to work them:**
1. Staff change the frame, or the CONTRACT and spec (DESIGN 6.5, the stub, and
   `tools/contracts.json` via `--write-contracts`).
2. Write a follow-up task that reopens the page. Carry its old acceptance tests over, adjusted.
3. Validate it on `chatbook-oracle`.
4. The local LLM re-implements it through the harness.

| # | Where | Problem | Proposed fix | Severity |
|---|---|---|---|---|
| 1 | cb-18 page_chat + frame `CB.go` | "Show older" navigates with `CB.go`. That re-mounts the page: the unsent draft is lost and the list jumps to the newest message | Option 1: `more[params.id]` counter + `CB.refresh()` (CONTRACT change; new hidden test checks the draft is kept and no navigation happens). Option 2: frame keeps typed values and scroll position on a `CB.go` to the same page | medium (UX; no sent data lost) |
| 2 | cb-18 page_chat | "Show older" fails past 200 messages (server caps `limit` at 200) | Page caps at 200 and hides the button; or the history API gains a `before` cursor | medium |
| 3 | cb-18 page_chat / chat helpers | "Seen" shows after a member is added even though nobody read the message | Define "Seen" as "every other member's last_read >= my last message", excluding members who joined after it; or show "Seen by n" | low |
| 4 | cb-22 badges + frame | A `/api/updates` response that lands after logout puts the old user's unread count back in the login page title (the only confirmed finding) | Frame: give each `CB.every` job a generation number and drop stale runs, and make `CB.badge` a no-op when logged out. Or CONTRACT: `if (!CB.me) return;` after the await | low |
| 5 | cb-18 / cb-20 pages | Sender names and member lines are plain text. DESIGN 1 says "click any name to open the profile" | Spec: render names as `#/profile?id=N` links | low |
| 6 | cb-21 page_profile | A multi-line bio shows on one line | `white-space: pre-wrap` class in the frame CSS + use it in the spec | low |
| 7 | frame (`cb.js`) | A polled page whose first load fails (e.g. the chat of a group you left) retries every poll: "Loading..." flashes and a new error toast appears each time | Frame: stop polling after a failed first load until the user retries | low |
| 8 | cb-15/16/21 pages | Action buttons stay enabled while their request runs (double click = 2 requests + false error toast); no refresh after a failed action; "Request sent" toast shows even when the request was auto-accepted; a 50+ char search lands on an error card | Frame: `CB.action` helper that disables the button while busy and refreshes after errors. Spec: toast text from the response; cap the search input at 50. **P2 notes from P1:** (1) also cover the Delete and Unlike buttons of the Activity page (cb-34). (2) page_post after an unfriend: a post page that was open before it lets you Unlike or Delete your own comment (200), but the refresh then toasts "post not found" and the stale page stays. Delete on your own comment that the post's author already deleted also toasts "post not found". Item 8's "refresh after errors" plus a leave-the-page-on-404 rule would fix both | low |
| 9 | cb-28 page_feed | Same class as item 2. "Show more" adds 20 to `limit` with no upper bound, but the feed API (cb-23) caps `limit` at 100. Once the feed shows 100 posts and `has_more` is still true, the next click navigates to `limit=120`; that load gets a 400 and the page shows the error card instead of the feed (cb-28 review) | CONTRACT + DESIGN 6.5: show "Show more" only while `Number(params.limit \|\| 20) < 100`, or page with the feed's `before` cursor. Add a hidden test for the cap | low |
| 10 | cb-24 likes, cb-25 comments. **In P1 (cb-31..cb-34)** | After an unfriend, a user can no longer delete their own comment, or remove their own like, on the ex-friend's post, and both stay visible to the post author's other friends. Every route checks `visible_post` first, as the CONTRACT requires (Wave 4 review `wf_946598bf-3c8`) | **Owner decided 2026-10-28: (a) plus a new "My activity" page** that lists your comments and likes on posts you can no longer see, with Delete / Unlike buttons (option (a) alone left no button in the app). The two options were: (a) the author check comes before `visible_post` for DELETE /api/comments/{id} (own comment) and DELETE /api/posts/{id}/like (own like), or (b) the frame's unfriend also removes each user's likes and comments on the other's posts. Change the CONTRACT, task.toml and tests, then re-run cb-24/cb-25. **P1 does this with new tasks instead of re-running cb-24/cb-25** (design `notes/polish-p1-design.md`, specs in DESIGN 6.5 "Polish P1"): cb-31-likes and cb-32-comments reopen the two files in place and carry the cb-24/cb-25 suites; cb-33-activity adds `GET /api/activity/hidden`, and cb-34-page_activity adds the "My activity" page. Frame commit `1fbb04a` | **medium** (privacy) |
| 11 | cb-25 comments. **In P1 (cb-31..cb-34)** | DELETE /api/comments/{id} answers 404 "post not found" for a comment on a post you can't see, but 404 "comment not found" for a missing id, so any user can probe which hidden comment ids exist (no other data leaks) | Spec: one 404 text for both cases (e.g. raise the same HTTPError as `visible_post`), plus a hidden test that compares the two bodies. **P1 does this:** in cb-32 a missing comment raises `HTTPError(404, "post not found")`, and in cb-31 a hidden post's unlike without my like raises the same 404. The tests compare the bodies with each other (DESIGN 3.1 exception) | low |
| 12 | cb-28 page_feed, cb-29 page_post (+ Unfriend, Leave group) | Delete acts on one click, with no confirm and no undo. Deleting a post also deletes everyone's comments and likes on it (Wave 5 review `wf_d4a98d27-b9a`) | Frame: a `CB.confirm(text) -> Promise<bool>` helper that the runner can answer from a scenario key, plus a `danger` button class. CONTRACTs: confirm before each DELETE. Tests: a declined confirm sends no DELETE. **P2 notes from P1:** also confirm the Activity page's Delete and Unlike (cb-34 has no confirm), and see item 8's page_post note | low |
| 13 | cb-28 / cb-29 | Line breaks typed into a post disappear when it is shown, because the frame's `pre-wrap` covers only `.msg`. Same fix as item 6 | Shared `pre-wrap` text class in cb.css; use it for post bodies, comments and bios in the CONTRACTs | low |
| 14 | cb-29 page_post | "Back to feed" goes to `feed` with no params, which drops the "Show more" depth | Pass the feed `limit` through (`post?id=N&limit=M`), or use `history.back()` via a frame helper | low |

**Frame tooling notes** (staff, from the CONTRACT-gate reviews):
- `--restore-contracts` skips a file that keeps only the stub's first line but deletes the rest of the
  block. The gate still reports it.
- A comment in `check_extra.main()` gives the wrong reason for `backslashreplace`: the harness forces
  UTF-8; the real reason is a cp874 console when run by hand.
- A retry prompt that carries a printed CONTRACT block can push the architect input over 5.5k tokens
  (cb-15: 5.7k). It still fits 8k. If it grows, print only the differing lines plus the block's first
  and last lines.
- The `run_page` runner (`tools/uirun.js`) skips the text of aria-hidden avatars and doesn't expose
  tag names. So no hidden test can catch a wrong avatar (e.g. `CB.avatar(CB.me)` instead of the
  author's) or h2-vs-h3 / span-vs-small swaps. Harmless so far (found by the cb-28..cb-30 reviews);
  expose `avatar` initials and `tag` in the runner result if it starts to matter.
- The stretch reviews found these cheap UI mutants that survive the hidden tests (low, not fixed):
  - cb-30: a global `CB.every(15000, CB.refresh)` instead of the page's `poll`;
  - cb-29: a parallel `Promise.all` load instead of two sequential GETs.

**Harness note:** cb-09's Aider applied a correct edit and then didn't exit until the 900 s timeout
(once in 23 runs). Watch for repeats.
