import importlib

import pytest

from chatbook.testing import Account, Client


def town(c: Client) -> dict[str, Account]:
    """Ids, usernames and display names all sort differently on purpose."""
    people = {
        "sally": c.user("sally", "Sally Moss"),  # 1: "al" in the username
        "kim": c.user("kim", "Kim Ng"),  # 2: the searcher
        "bert": c.user("bert", "Val Jordan"),  # 3: "al" in the display name only
        "abe": c.user("abe", "Abe Fox"),  # 4: first username, no match
        "alma": c.user("alma", "Alma Reyes"),  # 5: "al" in both
        "nora": c.user("nora", "Nora Lane"),  # 6: no "al", but "a l"
        "pascal": c.user("pascal", "Pascal Roy"),  # 7: "al" in the username
    }
    c.befriend(people["kim"], people["alma"])
    c.friend_request(people["sally"], people["kim"])
    c.friend_request(people["kim"], people["bert"])
    c.befriend(people["kim"], people["abe"])
    return people


def entry(a: Account, rel: str) -> dict[str, object]:
    return {"id": a.id, "username": a.username, "display_name": a.display_name, "relationship": rel}


def names(c: Client, path: str, who: Account) -> list[str]:
    r = c.get(path, user=who)
    assert r.status == 200
    return [u["username"] for u in r.json["users"]]


def test_matches_username_or_display_name_in_username_order() -> None:
    c = Client()
    p = town(c)
    r = c.get("/api/users?q=AL", user=p["kim"])
    assert r.status == 200
    assert r.json == {
        "users": [
            entry(p["alma"], "friends"),
            entry(p["bert"], "request_sent"),
            entry(p["pascal"], "none"),
            entry(p["sally"], "request_received"),
        ]
    }


def test_relationship_is_seen_from_the_searcher() -> None:
    c = Client()
    p = town(c)
    kim = entry(p["kim"], "")
    for viewer, rel in [("sally", "request_sent"), ("bert", "request_received"),
                        ("alma", "friends"), ("nora", "none")]:
        r = c.get("/api/users?q=kim", user=p[viewer])
        assert r.status == 200
        assert r.json == {"users": [kim | {"relationship": rel}]}


def test_the_searcher_is_never_listed() -> None:
    c = Client()
    p = town(c)
    assert names(c, "/api/users?q=al", p["pascal"]) == ["alma", "bert", "sally"]
    assert names(c, "/api/users?q=sally", p["sally"]) == []
    r = c.get("/api/users?q=Alma%20Reyes", user=p["alma"])
    assert (r.status, r.json) == (200, {"users": []})


def test_query_is_stripped_but_inner_spaces_count() -> None:
    c = Client()
    p = town(c)
    r = c.get("/api/users?q=%20%20VAL%20j%20", user=p["kim"])
    assert (r.status, r.json) == (200, {"users": [entry(p["bert"], "request_sent")]})
    assert names(c, "/api/users?q=a%20l", p["kim"]) == ["nora"]
    assert names(c, "/api/users?q=y%20M", p["kim"]) == ["sally"]
    assert names(c, "/api/users?q=y%20j", p["kim"]) == []


def test_no_match_gives_an_empty_list() -> None:
    c = Client()
    p = town(c)
    r = c.get("/api/users?q=xyz", user=p["kim"])
    assert (r.status, r.json) == (200, {"users": []})


def test_username_and_display_name_are_searched_separately() -> None:
    c = Client()
    otto = c.user("otto", "Otto Wu")
    c.user("rob", "Ertz Ann")
    assert names(c, "/api/users?q=robe", otto) == []
    assert names(c, "/api/users?q=bert", otto) == []
    assert names(c, "/api/users?q=b%20e", otto) == []
    assert names(c, "/api/users?q=n%20r", otto) == []
    assert names(c, "/api/users?q=ROB", otto) == ["rob"]
    assert names(c, "/api/users?q=ertz%20a", otto) == ["rob"]


def test_case_is_ignored_with_casefold() -> None:
    c = Client()
    otto = c.user("otto", "Otto Wu")
    c.user("quinn", "QUINN ROSS")
    c.user("anna", "Anna Strau\u00df")
    c.user("paul", "Paul Strauch")
    assert names(c, "/api/users?q=ross", otto) == ["quinn"]
    assert names(c, "/api/users?q=STRAUSS", otto) == ["anna"]
    assert names(c, "/api/users?q=Strau", otto) == ["anna", "paul"]


def test_percent_and_underscore_are_plain_characters() -> None:
    c = Client()
    otto = c.user("otto", "Otto Wu")
    pct = c.user("pct", "Pct 100%")
    c.user("j_doe", "Jo Doe")
    c.user("plain", "Plain Jane")
    r = c.get("/api/users?q=%25", user=otto)
    assert (r.status, r.json) == (200, {"users": [entry(pct, "none")]})
    assert names(c, "/api/users?q=_", otto) == ["j_doe"]
    assert names(c, "/api/users?q=0%25", otto) == ["pct"]


def test_limit_keeps_the_first_matches_after_filtering() -> None:
    c = Client()
    p = town(c)
    kim = p["kim"]
    assert names(c, "/api/users?q=al&limit=1", kim) == ["alma"]
    assert names(c, "/api/users?q=al&limit=2", kim) == ["alma", "bert"]
    assert names(c, "/api/users?q=al&limit=3", kim) == ["alma", "bert", "pascal"]
    assert names(c, "/api/users?q=al&limit=50", kim) == ["alma", "bert", "pascal", "sally"]
    assert names(c, "/api/users?q=al&limit=", kim) == ["alma", "bert", "pascal", "sally"]


def test_default_limit_is_20_and_max_is_50() -> None:
    c = Client()
    viewer = c.user("pat", "Pat Lo")
    for n in range(54, -1, -1):  # created in reverse, so ids run against username order
        c.user(f"m{n:02d}", f"Member {n}")
    expected = [f"m{n:02d}" for n in range(55)]
    assert names(c, "/api/users?q=M", viewer) == expected[:20]
    assert names(c, "/api/users?q=m&limit=21", viewer) == expected[:21]
    assert names(c, "/api/users?q=mem&limit=50", viewer) == expected[:50]


def test_query_of_50_characters_is_accepted() -> None:
    c = Client()
    otto = c.user("otto", "Otto Wu")
    long_name = "Maximilian Bartholomew Fitzgerald-Ostrowski Junior"
    assert len(long_name) == 50
    c.user("max", long_name)
    assert names(c, "/api/users?q=" + long_name.upper().replace(" ", "%20"), otto) == ["max"]
    assert names(c, "/api/users?q=%20%20" + "x" * 50 + "%20", otto) == []


@pytest.mark.parametrize("query", [
    "", "?q=", "?limit=5", "?q=%20%20%20", "?q=" + "y" * 51, "?q=al&limit=0", "?q=al&limit=51",
    "?q=al&limit=abc", "?q=al&limit=-3", "?q=al&limit=2.5", "?q=al&limit=1e1",
])
def test_bad_query_is_400(query: str) -> None:
    c = Client()
    p = town(c)
    assert c.get("/api/users" + query, user=p["kim"]).status == 400


def test_login_is_required() -> None:
    c = Client()
    town(c)
    assert c.get("/api/users?q=al").status == 401


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.people.handler")
