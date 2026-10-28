import importlib

import pytest

from chatbook.testing import Account, Client


def add(c: Client, cid: object, who: Account, body: object) -> tuple[int, object]:
    r = c.post(f"/api/groups/{cid}/members", body, user=who)
    return r.status, r.json


def leave(c: Client, cid: object, who: Account) -> tuple[int, object]:
    r = c.delete(f"/api/groups/{cid}/members/me", user=who)
    return r.status, r.json


def member_rows(c: Client, cid: int) -> list[dict[str, object]]:
    return c.rows(
        "SELECT conversation_id, user_id, joined_at, last_read_id FROM members"
        " WHERE conversation_id = ? ORDER BY user_id",
        cid,
    )


def members(c: Client, cid: int) -> list[object]:
    return [r["user_id"] for r in member_rows(c, cid)]


# -- add: success -------------------------------------------------------------------------


def test_add_friend_answers_the_group_as_the_caller_sees_it() -> None:
    c = Client()
    nora = c.user("nora", "Nora Nash")
    omar = c.user("omar", "Omar Ortiz")
    pia = c.user("pia", "Pia Park")
    c.dm(nora, omar)  # the group is not conversation 1
    g = c.group(nora, [omar], "Book club")
    c.tick(2000)
    c.send(omar, g, "chapter one")
    c.tick(3000)
    last = c.send(omar, g, "chapter two")
    sent_at = c.now
    c.befriend(nora, pia)
    c.tick(4000)
    status, body = add(c, g, nora, {"user_id": pia.id})
    assert status == 200
    assert body == {
        "conversation": {
            "id": g,
            "kind": "group",
            "title": "Book club",
            "members": [nora.json, omar.json, pia.json],
            "last_message": c.message(last),
            "unread": 2,
            "updated_at": sent_at,
        }
    }
    assert members(c, g) == [nora.id, omar.id, pia.id]


def test_new_member_row_and_only_later_messages_unread() -> None:
    c = Client()
    ravi = c.user("ravi", "Ravi Rao")
    sven = c.user("sven", "Sven Sol")
    tara = c.user("tara", "Tara Tam")
    g = c.group(ravi, [sven], "Garden")
    c.send(sven, g, "seeds")
    c.send(ravi, g, "pots")
    last = c.send(sven, g, "water")
    c.befriend(ravi, tara)
    before = member_rows(c, g)
    c.tick(6000)
    assert add(c, g, ravi, {"user_id": tara.id})[0] == 200
    joined = {"conversation_id": g, "user_id": tara.id, "joined_at": c.now, "last_read_id": last}
    assert member_rows(c, g) == [*before, joined]
    assert c.unread(tara, g) == 0
    assert c.unread(ravi, g) == 1
    c.tick(1000)
    c.send(sven, g, "sun")
    c.send(ravi, g, "rain")
    assert c.unread(tara, g) == 2


def test_members_sorted_by_id_and_group_without_messages() -> None:
    c = Client()
    zack = c.user("zack", "Zack Zorn")
    uma = c.user("uma", "Uma Ueda")
    vic = c.user("vic", "Vic Vance")
    g = c.group(vic, [uma], "Trail crew")
    created = c.now
    c.befriend(vic, zack)
    c.tick(9000)
    status, body = add(c, g, vic, {"user_id": zack.id})
    assert status == 200
    assert body == {
        "conversation": {
            "id": g,
            "kind": "group",
            "title": "Trail crew",
            "members": [zack.json, uma.json, vic.json],
            "last_message": None,
            "unread": 0,
            "updated_at": created,
        }
    }


def test_any_member_can_add_their_own_friend() -> None:
    c = Client()
    wren = c.user("wren", "Wren Wolfe")
    xavi = c.user("xavi", "Xavi Xu")
    yara = c.user("yara", "Yara Young")
    g = c.group(wren, [xavi], "Choir")
    c.send(xavi, g, "warm up")
    c.send(wren, g, "scales")
    c.send(wren, g, "song")
    c.befriend(xavi, yara)
    status, body = add(c, g, xavi, {"user_id": yara.id})
    assert status == 200
    assert body == {"conversation": c.conversation(g, xavi)}
    assert body["conversation"]["members"] == [wren.json, xavi.json, yara.json]
    assert body["conversation"]["unread"] == 2
    assert members(c, g) == [wren.id, xavi.id, yara.id]


def test_add_changes_only_the_named_group() -> None:
    c = Client()
    abe = c.user("abe", "Abe Arno")
    bea = c.user("bea", "Bea Bloom")
    cy = c.user("cy", "Cy Cole")
    g1 = c.group(abe, [bea], "First")
    g2 = c.group(abe, [bea], "Second")
    g3 = c.group(bea, [abe], "Third")
    c.befriend(abe, cy)
    status, body = add(c, g2, abe, {"user_id": cy.id})
    assert status == 200
    assert body == {"conversation": c.conversation(g2, abe)}
    assert body["conversation"]["title"] == "Second"
    assert members(c, g1) == [abe.id, bea.id]
    assert members(c, g2) == [abe.id, bea.id, cy.id]
    assert members(c, g3) == [abe.id, bea.id]


def test_member_who_left_can_be_added_back() -> None:
    c = Client()
    dov = c.user("dov", "Dov Dunn")
    eli = c.user("eli", "Eli Eng")
    fay = c.user("fay", "Fay Fern")
    g = c.group(dov, [eli, fay], "Runners")
    c.befriend(dov, eli)
    c.send(eli, g, "5k?")
    c.leave(eli, g)
    c.send(fay, g, "10k")
    last = c.send(dov, g, "both")
    c.tick(2500)
    status, body = add(c, g, dov, {"user_id": eli.id})
    assert status == 200
    assert body["conversation"]["members"] == [dov.json, eli.json, fay.json]
    assert c.row(
        "SELECT joined_at, last_read_id FROM members WHERE conversation_id = ? AND user_id = ?",
        g,
        eli.id,
    ) == {"joined_at": c.now, "last_read_id": last}
    assert c.unread(eli, g) == 0


# -- add: errors --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "link", ["stranger", "friend_of_a_member", "request_sent", "request_received", "unfriended"]
)
def test_adding_someone_who_is_not_my_friend_is_403(link: str) -> None:
    c = Client()
    kim = c.user("kim", "Kim Kerr")
    lou = c.user("lou", "Lou Lam")
    moe = c.user("moe", "Moe Mars")
    g = c.group(kim, [lou], "Band")
    if link == "friend_of_a_member":
        c.befriend(lou, moe)
    elif link == "request_sent":
        c.friend_request(kim, moe)
    elif link == "request_received":
        c.friend_request(moe, kim)
    elif link == "unfriended":
        c.befriend(kim, moe)
        c.unfriend(moe, kim)
    status, _ = add(c, g, kim, {"user_id": moe.id})
    assert status == 403
    assert members(c, g) == [kim.id, lou.id]


@pytest.mark.parametrize("case", ["member", "creator"])
def test_adding_a_current_member_is_409(case: str) -> None:
    c = Client()
    ada = c.user("ada", "Ada Ames")
    ben = c.user("ben", "Ben Bell")
    cal = c.user("cal", "Cal Cruz")
    g = c.group(ada, [ben, cal], "Lab")
    c.befriend(ada, cal)
    c.befriend(ben, ada)
    before = member_rows(c, g)
    if case == "member":
        status, _ = add(c, g, ada, {"user_id": cal.id})
    else:
        status, _ = add(c, g, ben, {"user_id": ada.id})
    assert status == 409
    assert member_rows(c, g) == before


@pytest.mark.parametrize("case", ["member", "creator"])
def test_adding_myself_is_409(case: str) -> None:
    # The caller is in member_ids at step 5, so adding yourself is "already a member".
    c = Client()
    hugo = c.user("hugo", "Hugo Hale")
    iris = c.user("iris", "Iris Ito")
    g = c.group(hugo, [iris], "Darts")
    who = iris if case == "member" else hugo
    before = member_rows(c, g)
    status, _ = add(c, g, who, {"user_id": who.id})
    assert status == 409
    assert member_rows(c, g) == before


def test_adding_the_same_friend_twice_is_409() -> None:
    c = Client()
    gil = c.user("gil", "Gil Grant")
    hal = c.user("hal", "Hal Hart")
    ivo = c.user("ivo", "Ivo Ivers")
    g = c.group(gil, [hal], "Chess")
    c.befriend(gil, ivo)
    assert add(c, g, gil, {"user_id": ivo.id})[0] == 200
    before = member_rows(c, g)
    c.tick(1000)
    status, _ = add(c, g, gil, {"user_id": ivo.id})
    assert status == 409
    assert member_rows(c, g) == before


@pytest.mark.parametrize("uid", [999, 6])
def test_adding_an_unknown_user_is_404(uid: int) -> None:
    c = Client()
    jo = c.user("jo", "Jo Jett")
    ken = c.user("ken", "Ken Knox")
    lia = c.user("lia", "Lia Lowe")
    c.befriend(jo, lia)
    g = c.group(jo, [ken], "Quiz")
    status, _ = add(c, g, jo, {"user_id": uid})
    assert status == 404
    assert members(c, g) == [jo.id, ken.id]


@pytest.mark.parametrize("caller", ["outsider", "member_who_left"])
def test_non_member_cannot_add_404(caller: str) -> None:
    c = Client()
    ida = c.user("ida", "Ida Imre")
    jay = c.user("jay", "Jay Jones")
    kai = c.user("kai", "Kai Kato")
    lee = c.user("lee", "Lee Lowe")
    mel = c.user("mel", "Mel Moss")
    c.group(lee, [ida], "Elsewhere")  # the outsider is a member of another group
    g = c.group(ida, [jay, kai], "Crew")
    if caller == "outsider":
        who = lee
    else:
        who = kai
        c.leave(kai, g)
    c.befriend(who, mel)
    before = members(c, g)
    status, _ = add(c, g, who, {"user_id": mel.id})
    assert status == 404
    assert members(c, g) == before


@pytest.mark.parametrize("raw", ["4444", "abc", "0", "-2", "1.5", "12345678901234567890"])
def test_add_with_unknown_or_malformed_group_id_is_404(raw: str) -> None:
    c = Client()
    ned = c.user("ned", "Ned Noble")
    oli = c.user("oli", "Oli Orr")
    pat = c.user("pat", "Pat Pine")
    g = c.group(ned, [oli], "Supper")
    c.befriend(ned, pat)
    status, _ = add(c, raw, ned, {"user_id": pat.id})
    assert status == 404
    assert members(c, g) == [ned.id, oli.id]


def test_adding_to_a_direct_conversation_is_400() -> None:
    c = Client()
    quinn = c.user("quinn", "Quinn Quill")
    rosa = c.user("rosa", "Rosa Reyes")
    sid = c.user("sid", "Sid Sharp")
    c.group(quinn, [rosa], "Real group")
    d = c.dm(rosa, quinn)
    c.befriend(quinn, sid)
    status, _ = add(c, d, quinn, {"user_id": sid.id})
    assert status == 400
    assert members(c, d) == [quinn.id, rosa.id]
    assert c.row("SELECT kind FROM conversations WHERE id = ?", d) == {"kind": "direct"}


@pytest.mark.parametrize(
    "body",
    [
        {"user_id": "7"},
        {"user_id": True},
        {"user_id": 0},
        {"user_id": -4},
        {"user_id": 2.5},
        {"user_id": None},
        {"user_id": [3]},
        {"member_id": 3},
        {},
        [3],
        "3",
        None,
    ],
)
def test_add_with_bad_user_id_is_400(body: object) -> None:
    c = Client()
    tom = c.user("tom", "Tom Tate")
    una = c.user("una", "Una Urban")
    val = c.user("val", "Val Vega")
    c.befriend(tom, val)
    g = c.group(tom, [una], "Picnic")
    status, _ = add(c, g, tom, body)
    assert status == 400
    assert members(c, g) == [tom.id, una.id]


# -- add: check order (each request breaks two checks; the earlier check answers) --------


@pytest.mark.parametrize("case", ["member", "creator"])
def test_a_current_member_who_is_not_my_friend_is_409(case: str) -> None:
    # Step 5 (already a member, 409) comes before step 6 (not my friend, 403).
    c = Client()
    jade = c.user("jade", "Jade Joy")
    kurt = c.user("kurt", "Kurt Kim")
    lena = c.user("lena", "Lena Lux")
    g = c.group(kurt, [jade, lena], "Pottery")
    c.befriend(kurt, lena)
    target = lena if case == "member" else kurt
    assert not c.are_friends(jade, target)
    before = member_rows(c, g)
    status, _ = add(c, g, jade, {"user_id": target.id})
    assert status == 409
    assert member_rows(c, g) == before


@pytest.mark.parametrize("target", ["bad_id", "member", "stranger"])
def test_an_outsider_is_404_whatever_the_body(target: str) -> None:
    # Step 1 (caller not a member, 404) comes before step 3 (bad user_id, 400), step 5
    # (already a member, 409) and step 6 (not my friend, 403).
    c = Client()
    mona = c.user("mona", "Mona Moor")
    nils = c.user("nils", "Nils Nye")
    otto = c.user("otto", "Otto Oak")
    rudy = c.user("rudy", "Rudy Ross")
    c.group(otto, [rudy], "Otto's own")
    g = c.group(mona, [nils], "Sailing")
    c.befriend(otto, nils)
    bodies: dict[str, object] = {
        "bad_id": {"user_id": "q"},
        "member": {"user_id": nils.id},
        "stranger": {"user_id": rudy.id},
    }
    status, _ = add(c, g, otto, bodies[target])
    assert status == 404
    assert members(c, g) == [mona.id, nils.id]


@pytest.mark.parametrize("target", ["unknown", "member", "stranger"])
def test_a_direct_conversation_is_400_whatever_the_user(target: str) -> None:
    # Step 2 (not a group, 400) comes before step 4 (unknown user, 404), step 5 (already a
    # member, 409) and step 6 (not my friend, 403).
    c = Client()
    pete = c.user("pete", "Pete Pratt")
    rhea = c.user("rhea", "Rhea Rowe")
    saul = c.user("saul", "Saul Sims")
    d = c.dm(pete, rhea)
    uid = {"unknown": 888, "member": rhea.id, "stranger": saul.id}[target]
    status, _ = add(c, d, pete, {"user_id": uid})
    assert status == 400
    assert members(c, d) == [pete.id, rhea.id]


# -- leave --------------------------------------------------------------------------------


def test_leave_removes_only_my_membership() -> None:
    c = Client()
    pam = c.user("pam", "Pam Pike")
    quin = c.user("quin", "Quin Quay")
    rex = c.user("rex", "Rex Roy")
    other = c.group(quin, [pam], "Other")
    c.dm(pam, quin)
    g = c.group(pam, [quin, rex], "Movie night")
    c.send(pam, g, "friday?")
    c.send(quin, g, "yes")
    c.send(rex, g, "maybe")
    rows = member_rows(c, g)
    assert leave(c, g, quin) == (200, {"left": g})
    assert member_rows(c, g) == [r for r in rows if r["user_id"] != quin.id]
    assert members(c, other) == [pam.id, quin.id]
    assert len(c.rows("SELECT id FROM messages WHERE conversation_id = ?", g)) == 3
    assert c.row("SELECT kind, title, created_by FROM conversations WHERE id = ?", g) == {
        "kind": "group",
        "title": "Movie night",
        "created_by": pam.id,
    }


def test_creator_can_leave() -> None:
    c = Client()
    sal = c.user("sal", "Sal Stone")
    ted = c.user("ted", "Ted Trent")
    ulf = c.user("ulf", "Ulf Unger")
    g = c.group(sal, [ted, ulf], "Hikers")
    assert leave(c, g, sal) == (200, {"left": g})
    assert members(c, g) == [ted.id, ulf.id]
    assert c.row("SELECT created_by FROM conversations WHERE id = ?", g) == {"created_by": sal.id}


def test_last_member_leaving_keeps_the_conversation_and_messages() -> None:
    c = Client()
    vera = c.user("vera", "Vera Voss")
    walt = c.user("walt", "Walt Wynn")
    c.group(walt, [vera], "Spare")
    g = c.group(vera, [walt], "Duo")
    mid = c.send(walt, g, "see you")
    c.leave(walt, g)
    assert leave(c, g, vera) == (200, {"left": g})
    assert members(c, g) == []
    assert c.row("SELECT id, kind FROM conversations WHERE id = ?", g) == {"id": g, "kind": "group"}
    assert c.message(mid)["body"] == "see you"


def test_leaving_twice_is_404() -> None:
    c = Client()
    xia = c.user("xia", "Xia Xing")
    yves = c.user("yves", "Yves Yale")
    zoe = c.user("zoe", "Zoe Zeal")
    g = c.group(xia, [yves, zoe], "Trio")
    assert leave(c, g, zoe) == (200, {"left": g})
    status, _ = leave(c, g, zoe)
    assert status == 404
    assert members(c, g) == [xia.id, yves.id]


def test_non_member_cannot_leave_404() -> None:
    c = Client()
    amy = c.user("amy", "Amy Akers")
    bo = c.user("bo", "Bo Barr")
    cole = c.user("cole", "Cole Cain")
    c.group(cole, [amy], "Cole's group")
    g = c.group(amy, [bo], "Pair plus")
    status, _ = leave(c, g, cole)
    assert status == 404
    assert members(c, g) == [amy.id, bo.id]


@pytest.mark.parametrize("raw", ["5555", "xyz", "0", "-1", "2.0", "99999999999999999999"])
def test_leave_with_unknown_or_malformed_group_id_is_404(raw: str) -> None:
    c = Client()
    dee = c.user("dee", "Dee Dale")
    eve = c.user("eve", "Eve Elm")
    g = c.group(dee, [eve], "Book swap")
    status, _ = leave(c, raw, dee)
    assert status == 404
    assert members(c, g) == [dee.id, eve.id]


def test_leaving_a_direct_conversation_is_400() -> None:
    c = Client()
    finn = c.user("finn", "Finn Ford")
    gwen = c.user("gwen", "Gwen Gale")
    c.group(gwen, [finn], "Not this one")
    d = c.dm(gwen, finn)
    status, _ = leave(c, d, finn)
    assert status == 400
    assert members(c, d) == [finn.id, gwen.id]


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.group_members.handler")
