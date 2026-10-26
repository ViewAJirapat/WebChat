"""The browser runtime (core/static/cb.js) through the headless runner, with the sample page."""

import re
from pathlib import Path
from typing import Any

import pytest

from chatbook.testing import ALICE, ERIN, UiResult, run_page, run_scenario

REPO = Path(__file__).resolve().parents[1]
CB_JS = REPO / "src" / "chatbook" / "core" / "static" / "cb.js"
SAMPLE = str(Path(__file__).resolve().parent / "fixtures" / "sample_page.js")
COUNT = "/api/sample/count"
DATA: dict[str, Any] = {
    "owner": ERIN,
    "note": "abcdefghijklmnop",
    "items": [{"id": 4, "name": "Pear", "likes": 2}, {"id": 6, "name": "Fig", "likes": 1}],
}
LOGIN_JS = "CB.page('login', {title: 'Welcome', public: true, render: () => 'Please log in'});\n"
INBOX_JS = "CB.page('inbox', {title: 'Chats', render: () => 'Inbox here'});\n"
# The worker-facing toolkit (DESIGN 3.13, docs/ui.md) and the globals the runner must not have.
TOOLKIT = [
    "page",
    "api",
    "el",
    "form",
    "go",
    "refresh",
    "every",
    "me",
    "login",
    "logout",
    "reloadMe",
    "avatar",
    "userLink",
    "time",
    "plural",
    "short",
    "toast",
    "badge",
    "qs",
]
NO_GLOBALS = [
    "document",
    "window",
    "fetch",
    "setTimeout",
    "setInterval",
    "require",
    "process",
    "localStorage",
]
PROBE_JS = (
    "const names = [" + ", ".join(f"'{n}'" for n in TOOLKIT) + "];\n"
    "const types = {" + ", ".join(f"{g}: typeof {g}" for g in NO_GLOBALS) + "};\n"
    "const present = Object.keys(types).filter((g) => types[g] !== 'undefined');\n"
    "CB.page('probe', {title: 'Probe', public: true, render: () => CB.el('div', {},\n"
    "  CB.el('p', {}, 'missing: [' + names.filter((n) => !(n in CB)).join(',') + ']'),\n"
    "  CB.el('p', {}, 'globals: [' + present.join(',') + ']'),\n"
    "  CB.el('p', {}, 'me: ' + (CB.me ? CB.me.username : 'none')),\n"
    "  CB.el('p', {}, 'time: ' + typeof CB.time(1700000000000)))});\n"
)


def run(
    page: str | None = "sample",
    *,
    api: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    me: dict[str, Any] | None = ALICE,
    params: dict[str, str] | None = None,
    files: list[str] | None = None,
) -> UiResult:
    full = {"GET /api/sample": DATA, "GET " + COUNT: {"n": 0}} | (api or {})
    return run_page(
        "sample", page, params=params, me=me, api=full, steps=steps, files=files or [SAMPLE]
    )


def page_calls(res: UiResult) -> list[list[Any]]:
    """The calls without the CB.every job's."""
    return [c for c in res.calls if c[1] != COUNT]


def form(res: UiResult, submit: str) -> dict[str, Any]:
    found = [f for f in res.forms if f["submit"] == submit]
    assert len(found) == 1, res.forms
    return found[0]


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


# --- load and render --------------------------------------------------------------------


def test_load_then_render() -> None:
    res = run()
    assert res.errors == [] and res.unmatched == [] and res.toasts == []
    assert page_calls(res) == [["GET", "/api/sample", None]]
    assert (res.page, res.title) == ("sample", "Sample")
    for part in [
        "Sample all",
        "Erin Evans",
        "Signed in as Alice Adams",
        "Renders: 1",
        "abcdefghij...",
        "Pear: 2 likes Like",
        "Fig: 1 like Like",
    ]:
        assert part in res.text
    assert "abcdefghijk" not in res.text
    assert ["raw", "<i>raw</i>5AB"] in res.classes  # text is text; null/false/undefined skipped
    assert ["avatar", ""] in res.classes  # aria-hidden: skipped in text
    assert ["user-link", "Erin Evans"] in res.classes
    assert ["item", "Pear: 2 likes Like"] in res.classes
    assert {"label": "Locked", "disabled": True, "testid": None} in res.buttons
    assert {"label": "Like", "disabled": False, "testid": "like-4"} in res.buttons


def test_form_description() -> None:
    add = form(run(), "Add")
    assert add["fields"] == ["name", "kind", "tags", "note", "secret"]
    assert add["types"] == {
        "name": "text",
        "kind": "select",
        "tags": "checkboxes",
        "note": "textarea",
        "secret": "password",
    }
    assert add["options"]["kind"] == ["a", "b"]
    assert add["options"]["tags"] == ["1", "2"]
    assert (add["values"]["name"], add["values"]["kind"], add["values"]["note"]) == ("", "b", "")


def test_poll_reruns_load_and_render() -> None:
    res = run(steps=[{"tick": 500}, {"tick": 500}, {"tick": 1000}])
    assert res.errors == []
    assert res.count("GET", "/api/sample") == 3
    assert "Renders: 3" in res.text


def test_refresh_and_coalesced_refreshes() -> None:
    # 'Reload' (exact label, though 'Reload thrice' comes first): one more load;
    # three refreshes in a row: one runs, the two requested meanwhile run once afterwards
    res = run(steps=[{"click": "Reload"}, {"click": "thrice"}])
    assert res.errors == []
    assert res.count("GET", "/api/sample") == 4
    assert "Renders: 4" in res.text


def test_load_error_shows_a_retry_card() -> None:
    failing = {"GET /api/sample": [{"$status": 500, "error": "db down"}, DATA]}
    res = run(api=failing)
    assert res.errors == []
    assert "Could not load this page." in res.text
    assert "Retry" in res.labels
    assert res.toasts == ["db down"]
    res = run(api=failing, steps=[{"click": "Retry"}])
    assert res.errors == []
    assert "Pear: 2 likes" in res.text
    assert res.count("GET", "/api/sample") == 2


def test_other_load_errors_are_recorded() -> None:
    res = run(params={"boom": "1"})
    assert "Could not load this page." in res.text
    assert len(res.errors) == 1 and "boom in load" in res.errors[0]
    assert page_calls(res) == []


def test_a_failed_poll_keeps_the_page_and_the_typed_text() -> None:
    # only a failed FIRST load shows the error card; a failed poll toasts and keeps the page
    failing = {"GET /api/sample": [DATA, DATA, {"$status": 500, "error": "x"}, DATA]}
    steps: list[dict[str, Any]] = [
        {"fill": "Add", "values": {"name": "dra"}},
        {"tick": 1000},  # load 2: fine
        {"tick": 1000},  # load 3: the 500
    ]
    res = run(api=failing, steps=steps)
    assert res.errors == []
    assert res.toasts == ["x"]
    assert "Could not load this page." not in res.text
    assert "Renders: 2" in res.text  # the page of the last good load is still shown
    assert form(res, "Add")["values"]["name"] == "dra"
    res = run(api=failing, steps=[*steps, {"tick": 1000}])  # load 4: fine again
    assert res.errors == [] and res.toasts == ["x"]
    assert res.count("GET", "/api/sample") == 4
    assert "Renders: 3" in res.text
    assert form(res, "Add")["values"]["name"] == "dra"


STILL_JS = """let first = null;
let renders = 0;
CB.page('still', {
  title: 'Still', poll: 1000,
  load: () => CB.api('GET', '/api/still'),
  render: (d) => {
    renders += 1;
    const send = CB.el('button', {onclick: () => {
      send.disabled = true;
      send.textContent = 'Sending';
      CB.refresh();
    }}, 'Send');
    const root = CB.el('div', {class: 'stack'}, CB.el('p', {}, 'n=' + d.n), send,
      CB.el('button', {onclick: () => CB.toast(first.isConnected + ' ' + renders)}, 'Report'));
    if (first === null) first = root;
    return root;
  },
});
"""


def test_an_unchanged_poll_leaves_the_mounted_page_alone(tmp_path: Path) -> None:
    # load and render run on every poll; the same data and tree are not mounted again, so
    # the nodes the user is pressing, selecting or focusing stay in place
    still = write(tmp_path, "still.js", STILL_JS)
    api = {"GET /api/still": [{"n": 1}, {"n": 1}, {"n": 1}, {"n": 2}]}
    steps: list[dict[str, Any]] = [{"tick": 1000}, {"tick": 1000}, {"click": "Report"}]
    res = run_page("still", "still", api=api, steps=steps, files=[still])
    assert res.errors == []
    assert res.toasts == ["true 3"]  # three renders, the first tree still mounted
    res = run_page("still", "still", api=api, steps=steps * 2, files=[still])
    assert res.errors == []
    assert res.toasts == ["true 3", "false 5"]  # n changed: the new tree replaced it
    assert "n=2" in res.text


def test_a_page_changed_by_its_own_code_is_mounted_again(tmp_path: Path) -> None:
    # the click disabled and relabelled its button, then refreshed with the same data:
    # the page is rendered and mounted again, as before the change
    still = write(tmp_path, "still.js", STILL_JS)
    res = run_page(
        "still",
        "still",
        api={"GET /api/still": {"n": 1}},
        steps=[{"click": "Send"}],
        files=[still],
    )
    assert res.errors == []
    assert res.count("GET", "/api/still") == 2
    assert {"label": "Send", "disabled": False, "testid": None} in res.buttons
    assert "Sending" not in res.text


# --- forms ------------------------------------------------------------------------------


def test_typed_text_survives_poll_and_refresh() -> None:
    steps: list[dict[str, Any]] = [
        {"fill": "Add", "values": {"name": "dra", "note": "line one"}},
        {"tick": 1000},
        {"click": "Reload"},
    ]
    res = run(steps=steps)
    assert res.errors == []
    assert res.count("GET", "/api/sample") == 3
    values = form(res, "Add")["values"]
    assert (values["name"], values["note"]) == ("dra", "line one")
    assert form(res, "Find")["values"]["q"] == ""


def test_submit_sends_values_then_resets_text_fields() -> None:
    values = {"name": "Kiwi", "kind": "a", "tags": ["2"], "note": "n1", "secret": "pw"}
    res = run(api={"POST /api/sample": {}}, steps=[{"submit": "Add", "values": values}])
    assert res.errors == []
    assert ["POST", "/api/sample", values] in res.calls
    assert res.count("GET", "/api/sample") == 2
    after = form(res, "Add")["values"]
    assert (after["name"], after["note"], after["secret"]) == ("", "", "")


def test_failed_submit_toasts_and_keeps_the_text() -> None:
    res = run(
        api={"POST /api/sample": {"$status": 400, "error": "name taken"}},
        steps=[{"submit": "Add", "values": {"name": "Kiwi"}}],
    )
    assert res.errors == []
    assert res.toasts == ["name taken"]
    defaults = {"name": "Kiwi", "kind": "b", "tags": [], "note": "", "secret": ""}
    assert ["POST", "/api/sample", defaults] in res.calls
    assert res.count("GET", "/api/sample") == 1
    assert form(res, "Add")["values"]["name"] == "Kiwi"


def test_plain_onsubmit_and_go() -> None:
    res = run(steps=[{"submit": "Find", "values": {"q": " 9 "}}])
    assert res.errors == []
    assert res.nav == [["sample", {"id": "9"}]]
    assert ["GET", "/api/sample?id=9", None] in res.calls
    assert "Sample 9" in res.text


# --- server errors and the session ------------------------------------------------------


def test_api_error_is_toasted_not_recorded() -> None:
    res = run(
        api={"POST /api/sample/fail": {"$status": 400, "error": "nope"}},
        steps=[{"click": "Fail"}],
    )
    assert res.errors == []
    assert res.toasts == ["nope"]
    assert res.session == []


def test_api_error_without_a_message_toasts_the_status() -> None:
    res = run(api={"POST /api/sample/fail": {"$status": 503}}, steps=[{"click": "Fail"}])
    assert res.errors == []
    assert res.toasts == ["Request failed (503)"]


def test_401_while_logged_in_logs_out_and_stops_jobs() -> None:
    res = run(
        api={
            "POST /api/sample/fail": {"$status": 401, "error": "login required"},
            "DELETE /api/session": {"ok": True},
        },
        steps=[{"click": "Fail"}, {"tick": 4000}],
    )
    assert res.errors == []
    assert res.session == [["logout"]]
    assert res.toasts == ["login required"]
    assert ["DELETE", "/api/session", None] in res.calls
    assert res.count("GET", COUNT) == 1  # the job ran at start only
    assert res.count("GET", "/api/sample") == 1  # leaving the page stopped its poll


def test_401_while_logged_out_does_not_log_out() -> None:
    res = run(
        "sample_open",
        me=None,
        api={"GET /api/ping": {"$status": 401, "error": "login required"}},
        steps=[{"click": "Ping"}],
    )
    assert res.errors == []
    assert res.calls == [["GET", "/api/ping", None]]  # no CB.every job while logged out
    assert res.session == []
    assert res.toasts == ["login required"]
    assert res.page == "sample_open"


def test_login_starts_jobs_and_opens_inbox() -> None:
    zed = {"id": 9, "username": "zed", "display_name": "Zed Zu"}
    res = run(
        "sample_open",
        me=None,
        api={"POST /api/sample/login": {"token": "tok-9", "user": zed}, "GET " + COUNT: {"n": 2}},
        steps=[{"submit": "Sign in", "values": {"name": "zed"}}],
    )
    assert res.errors == []
    assert res.calls[0] == ["POST", "/api/sample/login", {"name": "zed"}]
    assert res.count("GET", COUNT) == 1
    assert res.session == [["login", "tok-9", zed]]
    assert res.nav == [["inbox", {}]]
    assert res.badges == {"sample": 2}


def test_reload_me() -> None:
    renamed = ALICE | {"display_name": "Alice Renamed"}
    res = run(api={"GET /api/session": {"user": renamed}}, steps=[{"click": "Who am I"}])
    assert res.errors == []
    assert ["GET", "/api/session", None] in res.calls
    assert "Signed in as Alice Renamed" in res.text


def test_every_job_runs_at_start_and_on_its_interval() -> None:
    res = run(api={"GET " + COUNT: {"n": 3}}, steps=[{"tick": 3999}, {"tick": 1}])
    assert res.errors == []
    assert res.count("GET", COUNT) == 2
    assert res.badges == {"sample": 3}


# --- navigation -------------------------------------------------------------------------


def test_go_converts_params_to_strings() -> None:
    res = run(steps=[{"click": "Open seven"}])
    assert res.errors == []
    assert res.nav == [["sample", {"id": "7", "flag": "true"}]]
    assert ["GET", "/api/sample?id=7", None] in res.calls
    assert "Sample 7" in res.text


def test_go_step_and_leaving_a_page_cancels_its_poll() -> None:
    res = run(steps=[{"go": "sample_open"}, {"tick": 1000}])
    assert res.errors == []
    assert res.nav == [["sample_open", {}]]
    assert res.page == "sample_open"
    assert "Ping" in res.labels
    assert res.count("GET", "/api/sample") == 1


def test_logged_out_visitor_of_a_private_page_gets_login(tmp_path: Path) -> None:
    login = write(tmp_path, "login.js", LOGIN_JS)
    res = run("sample", me=None, files=[SAMPLE, login])
    assert res.errors == []
    assert res.page == "login"
    assert "Please log in" in res.text
    assert res.calls == []


def test_logged_in_user_skips_login(tmp_path: Path) -> None:
    files = [write(tmp_path, "login.js", LOGIN_JS), write(tmp_path, "inbox.js", INBOX_JS)]
    res = run_page("x", "login", api={}, files=files)
    assert res.errors == []
    assert res.page == "inbox"
    assert "Inbox here" in res.text


def test_unknown_page_shows_not_found() -> None:
    res = run("nope")
    assert "Page not found" in res.text
    assert page_calls(res) == []


# --- helpers ----------------------------------------------------------------------------


def test_helpers() -> None:
    res = run(steps=[{"click": "Helpers"}])
    assert res.errors == []
    assert res.toasts == ["?a=1&b=x%20y", "[]", "1 friend", "3 friends", "abc...", "abc"]


def test_unknown_el_prop_and_banned_tag_throw() -> None:
    res = run(steps=[{"click": "Break"}, {"click": "Bad tag"}])
    assert len(res.errors) == 2
    assert 'unknown prop "href"' in res.errors[0]
    assert "script" in res.errors[1]
    assert not any(e.startswith("scenario:") for e in res.errors)


FORM_JS = """CB.page('handmade', {title: 'Handmade', render: () => CB.el('div', {},
  CB.el('button', {onclick: () => CB.el('form', {class: 'row'})}, 'Make form'))});
"""


def test_a_hand_built_form_is_refused(tmp_path: Path) -> None:
    # in the browser its submit would reload the page and put the fields in the URL
    page = write(tmp_path, "handmade.js", FORM_JS)
    res = run_page("handmade", "handmade", files=[page], steps=[{"click": "Make form"}])
    assert len(res.errors) == 1, res.errors
    assert 'CB.el: tag "form" is not allowed; use CB.form' in res.errors[0]
    assert "/ui/handmade.js:2" in res.errors[0]


def test_the_runner_reports_a_submit_nobody_prevents(tmp_path: Path) -> None:
    # a cb.js copy without the form ban stands in for any other way a plain form appears
    ban = "if (name === 'form') throw"
    source = CB_JS.read_text(encoding="utf-8")
    assert source.count(ban) == 1
    loose = write(tmp_path, "cb_loose.js", source.replace(ban, "if (false) throw"))
    page = write(
        tmp_path,
        "plain.js",
        "CB.page('plain', {title: 'Plain', render: () => CB.el('form', {},\n"
        "  CB.el('button', {type: 'submit', onclick: () => CB.toast('sent')}, 'Send'))});\n",
    )
    scenario = {"cb": loose, "files": [page], "me": ALICE, "page": "plain"}
    res = run_scenario(scenario | {"steps": [{"click": "Send"}]})
    assert res["toasts"] == ["sent"]
    assert res["errors"] == [
        "a form was submitted without CB.form: the browser would reload the page"
    ]
    res = run_scenario(
        scenario
        | {
            "files": [SAMPLE],
            "page": "sample",
            "api": {"GET /api/sample": DATA, "GET " + COUNT: {"n": 0}},
            "steps": [{"submit": "Find", "values": {"q": "3"}}],
        }
    )
    assert res["errors"] == []  # CB.form prevents the browser's submit


STRICT_JS = """CB.page('strict', {title: 'Strict', render: () => {
  const box = CB.el('div', {}, CB.el('span', {}, 'a'), CB.el('span', {}, 'b'));
  const sel = CB.el('select', {value: '2'});
  sel.append(CB.el('option', {value: '1'}, 'One'), CB.el('option', {value: '2'}, 'Two'));
  const later = CB.el('select', {}, CB.el('option', {value: '1'}, 'One'),
    CB.el('option', {value: '2'}, 'Two'));
  later.value = '2';
  const gone = CB.el('select', {}, CB.el('option', {value: '1'}, 'One'));
  gone.value = '9';
  const live = box.childNodes;
  box.append(CB.el('span', {}, 'c'));
  return CB.el('div', {},
    CB.el('button', {onclick: () => box.appendChild('text')}, 'Append text'),
    CB.el('button', {onclick: () => box.childNodes.map((n) => n)}, 'Map'),
    CB.el('button', {onclick: () => box.children.forEach((n) => n)}, 'Each'),
    CB.el('button', {onclick: () => CB.toast([sel.value, later.value, gone.value, live.length,
      Array.from(box.children).length, box.childNodes[2].textContent,
      typeof box.childNodes.forEach, typeof box.children.forEach].join(' '))}, 'Read'));
}});
"""


def test_the_fake_dom_is_as_strict_as_the_browser(tmp_path: Path) -> None:
    page = write(tmp_path, "strict.js", STRICT_JS)
    res = run_page("strict", "strict", files=[page], steps=[{"click": "Read"}])
    assert res.errors == []
    # Chrome: a value set before the options exist selects the first option; a value no
    # option has selects nothing; childNodes is live; only NodeList has forEach
    assert res.toasts == ["1 2  3 3 c function undefined"]
    for label, message in [
        ("Append text", "parameter 1 is not of type 'Node'"),
        ("Map", "map is not a function"),
        ("Each", "forEach is not a function"),
    ]:
        res = run_page("strict", "strict", files=[page], steps=[{"click": label}])
        assert len(res.errors) == 1, res.errors
        assert message in res.errors[0] and "/ui/strict.js:" in res.errors[0], res.errors


def test_the_documented_toolkit_exists_and_the_runner_has_no_browser_globals(
    tmp_path: Path,
) -> None:
    probe = write(tmp_path, "probe.js", PROBE_JS)
    for me, who in [(ALICE, "alice"), (None, "none")]:
        res = run_page("probe", "probe", me=me, files=[probe])
        assert res.errors == []
        assert "missing: []" in res.text
        assert "globals: []" in res.text
        assert f"me: {who}" in res.text
        assert "time: string" in res.text


def test_every_css_class_named_in_docs_ui_exists_in_cb_css() -> None:
    doc = (REPO / "docs" / "ui.md").read_text(encoding="utf-8")
    section = doc.split("## CSS classes", 1)[1].split("\n## ", 1)[0]
    names = re.findall(r"([a-z][a-z-]*)(?:\s*\([^)]*\))?\s*(?:,|$)", section, re.M)
    assert len(names) >= 12, names
    css = (REPO / "src" / "chatbook" / "core" / "static" / "cb.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # a class named in a comment does not count
    missing = [n for n in names if not re.search(rf"\.{n}(?![\w-])", css)]
    assert missing == []


# --- runner steps -----------------------------------------------------------------------


def test_click_nth_click_id_and_clickable_links() -> None:
    res = run(
        api={"POST /api/sample/6/like": {}, "POST /api/sample/4/like": {}},
        steps=[{"click": "Like", "nth": 1}, {"click_id": "like-4"}, {"click": "Erin Evans"}],
    )
    assert res.errors == [] and res.unmatched == []
    assert [c[1] for c in res.calls if c[0] == "POST"] == [
        "/api/sample/6/like",
        "/api/sample/4/like",
    ]
    assert res.count("GET", "/api/sample") == 3
    assert res.nav == [["profile", {"id": "5"}]]  # CB.userLink


def test_unmatched_call_is_recorded_and_answered_404() -> None:
    res = run(steps=[{"click": "Like"}])
    assert res.errors == []
    assert len(res.unmatched) == 1
    assert res.unmatched[0][:2] == ["POST", "/api/sample/4/like"]
    assert res.toasts == ["not found"]
    assert res.count("GET", "/api/sample") == 1


@pytest.mark.parametrize(
    "step",
    [
        {"click": "No such button"},
        {"click": "Locked"},  # disabled
        {"click_id": "nope-1"},
        {"fill": "Add", "values": {"nope": "x"}},
        {"fill": "Add", "values": {"kind": "z"}},
        {"fill": "Add", "values": {"tags": ["9"]}},
        {"submit": "No such form", "values": {}},
    ],
)
def test_scenario_problems_are_reported(step: dict[str, Any]) -> None:
    res = run(steps=[step])
    assert res.errors
    assert all(e.startswith("scenario:") for e in res.errors)


# --- one scope per file -----------------------------------------------------------------


def test_duplicate_page_name_is_an_error(tmp_path: Path) -> None:
    dup = write(tmp_path, "dup.js", "CB.page('sample', {title: 'Again', render: () => 'x'});\n")
    res = run(None, files=[SAMPLE, dup])
    assert any('page "sample" registered twice' in e for e in res.errors)


def test_each_file_gets_its_own_strict_scope(tmp_path: Path) -> None:
    other = write(
        tmp_path,
        "other.js",
        "const LABEL = 'Other';\n"
        "let renders = 100;\n"
        "let strict = false;\n"
        "try {\n"
        "  undeclaredName = 1;\n"
        "} catch (e) {\n"
        "  strict = e instanceof ReferenceError;\n"
        "}\n"
        "CB.page('other', {title: LABEL, render: () => CB.el('p', {},\n"
        "  LABEL + ' strict=' + strict + ' renders=' + renders)});\n",
    )
    res = run("other", files=[SAMPLE, other])
    assert res.errors == []
    assert "Other strict=true renders=100" in res.text
    assert {p["name"] for p in res.pages} == {"sample", "sample_open", "other"}
