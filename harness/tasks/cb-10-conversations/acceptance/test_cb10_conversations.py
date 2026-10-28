import importlib

import pytest

from chatbook.testing import Account, Client


def inbox(c: Client, who: Account) -> list[int]:
    """Ids of `who`'s conversation list, in the order the API returns them."""
    r = c.get("/api/conversations", user=who)
    assert r.status == 200
    assert set(r.json) == {"conversations"}
    return [item["id"] for item in r.json["conversations"]]


# -- GET /api/conversations ---------------------------------------------------------------


def test_list_puts_newest_activity_first_as_each_viewer_sees_it() -> None:
    c = Client()
    olga = c.user("olga", "Olga Ortiz")
    pete = c.user("pete", "Pete Park")
    rita = c.user("rita", "Rita Ruiz")
    d1 = c.dm(olga, pete)
    c.tick(4000)
    g = c.group(olga, [pete, rita], "Book club")
    c.tick(7000)
    m = c.send(pete, d1, "see you at noon")
    r = c.get("/api/conversations", user=olga)
    assert r.status == 200
    assert r.json == {"conversations": [c.conversation(d1, olga), c.conversation(g, olga)]}
    first = r.json["conversations"][0]
    assert first["title"] == "Pete Park"
    assert first["unread"] == 1
    assert first["last_message"] == c.message(m)
    assert first["updated_at"] == c.now
    r = c.get("/api/conversations", user=pete)
    assert r.status == 200
    assert r.json == {"conversations": [c.conversation(d1, pete), c.conversation(g, pete)]}
    assert r.json["conversations"][0]["title"] == "Olga Ortiz"
    assert r.json["conversations"][0]["unread"] == 0
    r = c.get("/api/conversations", user=rita)
    assert (r.status, r.json) == (200, {"conversations": [c.conversation(g, rita)]})


def test_list_item_is_the_full_conversation_shape() -> None:
    c = Client()
    c.user("pad", "Pad Person")
    vic = c.user("vic", "Vic Vance")
    wes = c.user("wes", "Wes Wong")
    c.tick(2500)
    created = c.now
    d = c.dm(wes, vic)
    c.tick(900)
    r = c.get("/api/conversations", user=vic)
    assert r.status == 200
    assert r.json == {
        "conversations": [
            {
                "id": d,
                "kind": "direct",
                "title": "Wes Wong",
                "members": [vic.json, wes.json],
                "last_message": None,
                "unread": 0,
                "updated_at": created,
            }
        ]
    }


def test_user_without_conversations_gets_empty_list() -> None:
    c = Client()
    kim = c.user("kim", "Kim Kerr")
    lou = c.user("lou", "Lou Lane")
    moss = c.user("moss", "Moss Moore")
    lonely = c.user("lonely", "Lonely Lark")
    c.befriend(lonely, kim)
    d = c.dm(kim, lou)
    c.group(lou, [kim, moss], "No lonely")
    c.send(kim, d, "ping")
    r = c.get("/api/conversations", user=lonely)
    assert (r.status, r.json) == (200, {"conversations": []})


def test_list_holds_only_my_current_conversations() -> None:
    c = Client()
    me = c.user("nora", "Nora Nash")
    ola = c.user("ola", "Ola Olsen")
    pam = c.user("pam", "Pam Price")
    quin = c.user("quin", "Quin Quay")
    theirs = c.dm(ola, pam)
    mine = c.dm(quin, me)
    c.tick()
    left = c.group(ola, [me, pam], "Left behind")
    c.tick()
    kept = c.group(pam, [quin, me], "Still here")
    c.tick()
    c.send(ola, theirs, "not for nora")
    c.send(pam, left, "after she left")
    c.leave(me, left)
    c.tick()
    without = c.group(ola, [pam, quin], "Without nora")
    assert inbox(c, me) == [kept, mine]
    assert inbox(c, ola) == [without, left, theirs]
    assert inbox(c, pam) == [without, left, theirs, kept]
    assert inbox(c, quin) == [without, kept, mine]
    r = c.get("/api/conversations", user=me)
    assert r.json == {"conversations": [c.conversation(kept, me), c.conversation(mine, me)]}


@pytest.mark.parametrize(
    ("sends", "order"),
    [
        ([], [3, 2, 1, 0]),
        ([0], [0, 3, 2, 1]),
        ([1, 0], [0, 1, 3, 2]),
        ([2, 2, 0, 2], [2, 0, 3, 1]),
        ([3, 1], [1, 3, 2, 0]),
        ([0, 1, 2, 3], [3, 2, 1, 0]),
        ([3, 2, 1, 0], [0, 1, 2, 3]),
        ([1, 1, 1], [1, 3, 2, 0]),
    ],
)
def test_list_order_follows_the_latest_message(sends: list[int], order: list[int]) -> None:
    c = Client()
    me = c.user("sara", "Sara Shaw")
    tom = c.user("tom", "Tom Tate")
    uma = c.user("uma", "Uma Ueda")
    val = c.user("val", "Val Vega")
    c.dm(tom, val)  # not mine
    convs = [c.dm(me, tom)]
    c.tick(1500)
    convs.append(c.group(val, [me, uma], "Alpha"))
    c.tick(1500)
    convs.append(c.dm(uma, me))
    c.tick(1500)
    convs.append(c.group(me, [tom, val], "Beta"))
    other = [tom, uma, uma, val]  # a member of each conversation besides me
    for n, i in enumerate(sends):
        c.tick(2000)
        c.send(me if n % 2 else other[i], convs[i], f"msg {n}")
    r = c.get("/api/conversations", user=me)
    assert r.status == 200
    assert r.json == {"conversations": [c.conversation(convs[i], me) for i in order]}


@pytest.mark.parametrize(
    ("sends", "order"),
    [
        ([2, 0], [2, 0, 3, 1]),
        ([0, 2], [2, 0, 3, 1]),
        ([3, 1, 0], [3, 1, 0, 2]),
        ([0, 1, 3], [3, 1, 0, 2]),
        ([1, 0, 1, 0], [1, 0, 3, 2]),
    ],
)
def test_same_time_messages_tie_by_conversation_id(sends: list[int], order: list[int]) -> None:
    c = Client()
    me = c.user("wren", "Wren Wade")
    xia = c.user("xia", "Xia Xu")
    yan = c.user("yan", "Yan Yee")
    convs = [c.dm(xia, me)]
    c.tick(1000)
    convs.append(c.group(me, [xia, yan], "Gamma"))
    c.tick(1000)
    convs.append(c.dm(me, yan))
    c.tick(1000)
    convs.append(c.group(yan, [me], "Delta"))
    c.tick(10_000)
    for n, i in enumerate(sends):  # all at the same time
        c.send(xia if i in (0, 1) else yan, convs[i], f"same time {n}")
    r = c.get("/api/conversations", user=me)
    assert r.status == 200
    assert r.json == {"conversations": [c.conversation(convs[i], me) for i in order]}


def test_conversations_created_together_tie_by_id_descending() -> None:
    c = Client()
    zed = c.user("zed", "Zed Zane")
    amy = c.user("amy", "Amy Ames")
    ben = c.user("ben", "Ben Bell")
    g1 = c.group(amy, [zed, ben], "First")
    d1 = c.dm(zed, amy)
    d2 = c.dm(ben, zed)
    g2 = c.group(ben, [zed], "Last")
    assert inbox(c, zed) == [g2, d2, d1, g1]
    assert inbox(c, amy) == [d1, g1]
    assert inbox(c, ben) == [g2, d2, g1]


def test_new_empty_conversation_can_outrank_an_older_message() -> None:
    c = Client()
    cy = c.user("cy", "Cy Cruz")
    deb = c.user("deb", "Deb Dunn")
    eli = c.user("eli", "Eli Esch")
    old = c.dm(cy, deb)
    c.tick(1000)
    c.send(deb, old, "early words")
    c.tick(3000)
    fresh = c.group(eli, [cy], "Fresh")
    assert inbox(c, cy) == [fresh, old]
    c.tick(3000)
    c.send(cy, old, "back again")
    assert inbox(c, cy) == [old, fresh]


# -- GET /api/conversations/{id} ----------------------------------------------------------


def test_detail_returns_conversation_and_reads() -> None:
    c = Client()
    fay = c.user("fay", "Fay Ford")
    gus = c.user("gus", "Gus Gill")
    d = c.dm(fay, gus)
    c.tick(1200)
    m1 = c.send(gus, d, "are you there")
    c.tick(1200)
    m2 = c.send(fay, d, "yes")
    r = c.get(f"/api/conversations/{d}", user=gus)
    assert r.status == 200
    assert r.json == {
        "conversation": c.conversation(d, gus),
        "reads": [
            {"user_id": fay.id, "last_read_id": m2},
            {"user_id": gus.id, "last_read_id": m1},
        ],
    }
    assert r.json["conversation"]["title"] == "Fay Ford"
    assert r.json["conversation"]["unread"] == 1
    assert r.json["conversation"]["last_message"] == c.message(m2)
    r = c.get(f"/api/conversations/{d}", user=fay)
    assert r.status == 200
    assert r.json["conversation"] == c.conversation(d, fay)
    assert r.json["conversation"]["title"] == "Gus Gill"


def test_detail_reads_follow_user_id_and_read_state() -> None:
    c = Client()
    hal = c.user("hal", "Hal Hart")
    ida = c.user("ida", "Ida Ives")
    jay = c.user("jay", "Jay Judd")
    kat = c.user("kat", "Kat Kemp")
    g = c.group(kat, [jay, hal, ida], "Hikers")
    c.tick()
    m1 = c.send(jay, g, "trail at 9")
    c.tick()
    m2 = c.send(kat, g, "ok")
    c.read(ida, g)
    r = c.get(f"/api/conversations/{g}", user=hal)
    assert r.status == 200
    assert r.json == {
        "conversation": c.conversation(g, hal),
        "reads": [
            {"user_id": hal.id, "last_read_id": 0},
            {"user_id": ida.id, "last_read_id": m2},
            {"user_id": jay.id, "last_read_id": m1},
            {"user_id": kat.id, "last_read_id": m2},
        ],
    }
    assert r.json["conversation"]["unread"] == 2
    c.leave(ida, g)
    c.read(hal, g)
    r = c.get(f"/api/conversations/{g}", user=kat)
    assert r.status == 200
    assert r.json == {
        "conversation": c.conversation(g, kat),
        "reads": [
            {"user_id": hal.id, "last_read_id": m2},
            {"user_id": jay.id, "last_read_id": m1},
            {"user_id": kat.id, "last_read_id": m2},
        ],
    }


def test_detail_of_a_conversation_without_messages() -> None:
    c = Client()
    for name in ["pad1", "pad2"]:
        c.user(name)
    lea = c.user("lea", "Lea Lund")
    moe = c.user("moe", "Moe Marsh")
    c.dm(lea, moe)
    c.tick(5000)
    created = c.now
    g = c.group(moe, [lea], "Quiet")
    c.tick(5000)
    r = c.get(f"/api/conversations/{g}", user=lea)
    assert r.status == 200
    assert r.json == {
        "conversation": {
            "id": g,
            "kind": "group",
            "title": "Quiet",
            "members": [lea.json, moe.json],
            "last_message": None,
            "unread": 0,
            "updated_at": created,
        },
        "reads": [
            {"user_id": lea.id, "last_read_id": 0},
            {"user_id": moe.id, "last_read_id": 0},
        ],
    }


def test_detail_writes_nothing() -> None:
    c = Client()
    nell = c.user("nell", "Nell Nunn")
    otis = c.user("otis", "Otis Ott")
    d = c.dm(nell, otis)
    c.send(otis, d, "unread one")
    c.send(otis, d, "unread two")
    assert c.get(f"/api/conversations/{d}", user=nell).status == 200
    assert c.get("/api/conversations", user=nell).status == 200
    assert c.unread(nell, d) == 2
    assert c.rows("SELECT user_id, last_read_id FROM members ORDER BY user_id") == [
        {"user_id": nell.id, "last_read_id": 0},
        {"user_id": otis.id, "last_read_id": 2},
    ]


def test_detail_for_outsider_is_404() -> None:
    c = Client()
    ned = c.user("ned", "Ned Noel")
    opal = c.user("opal", "Opal Orr")
    peg = c.user("peg", "Peg Pratt")
    d = c.dm(ned, opal)
    c.send(ned, d, "private")
    assert c.get(f"/api/conversations/{d}", user=peg).status == 404


def test_detail_after_leaving_is_404() -> None:
    c = Client()
    ray = c.user("ray", "Ray Rowe")
    sal = c.user("sal", "Sal Soto")
    ted = c.user("ted", "Ted Tran")
    g = c.group(ray, [sal, ted], "Leavers")
    c.send(sal, g, "bye")
    c.leave(ted, g)
    assert c.get(f"/api/conversations/{g}", user=ted).status == 404
    assert c.get(f"/api/conversations/{g}", user=sal).status == 200


@pytest.mark.parametrize("raw", ["987", "abc", "0", "-3", "2.0", "7x", "00"])
def test_detail_bad_or_unknown_id_is_404(raw: str) -> None:
    c = Client()
    ulf = c.user("ulf", "Ulf Upton")
    vi = c.user("vi", "Vi Voss")
    c.dm(ulf, vi)
    c.group(vi, [ulf], "Two")
    assert c.get(f"/api/conversations/{raw}", user=ulf).status == 404


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.conversations.handler")
