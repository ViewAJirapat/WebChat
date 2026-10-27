import importlib

from chatbook.testing import Client


def test_fresh_user_gets_all_zero_counts() -> None:
    c = Client()
    mia = c.user("mia", "Mia Moon")
    noah = c.user("noah", "Noah Ng")
    opal = c.user("opal", "Opal Orr")
    other_dm = c.dm(noah, opal)
    c.send(noah, other_dm, "hi opal")
    c.friend_request(noah, opal)
    r = c.get("/api/updates", user=mia)
    assert (r.status, r.json) == (
        200,
        {"unread_total": 0, "unread_conversations": 0, "friend_requests": 0},
    )


def test_updates_counts_unreads_across_conversations_and_incoming_requests() -> None:
    c = Client()
    lara = c.user("lara", "Lara Lin")
    max_u = c.user("max", "Max Moss")
    nina = c.user("nina", "Nina Nunn")
    owen = c.user("owen", "Owen Ott")
    pia = c.user("pia", "Pia Park")
    quin = c.user("quin", "Quin Quay")
    rex = c.user("rex", "Rex Roy")

    d1 = c.dm(lara, max_u)
    g = c.group(max_u, [lara, nina], "Project")
    outsider_dm = c.dm(nina, owen)

    c.send(max_u, d1, "msg 1")
    c.send(max_u, d1, "msg 2")
    c.send(nina, g, "group msg 1")
    c.send(nina, outsider_dm, "not for lara 1")
    c.send(owen, outsider_dm, "not for lara 2")

    c.friend_request(pia, lara)
    c.friend_request(quin, lara)
    c.friend_request(lara, rex)  # outgoing from lara: must not count for lara

    r = c.get("/api/updates", user=lara)
    assert (r.status, r.json) == (
        200,
        {"unread_total": 3, "unread_conversations": 2, "friend_requests": 2},
    )

    # Reading d1 clears its 2 unreads for lara, leaving 1 unread in g
    c.read(lara, d1)
    r_after_read = c.get("/api/updates", user=lara)
    assert (r_after_read.status, r_after_read.json) == (
        200,
        {"unread_total": 1, "unread_conversations": 1, "friend_requests": 2},
    )

    # Leaving g removes g from lara's unread counts
    c.leave(lara, g)
    r_after_leave = c.get("/api/updates", user=lara)
    assert (r_after_leave.status, r_after_leave.json) == (
        200,
        {"unread_total": 0, "unread_conversations": 0, "friend_requests": 2},
    )


def test_own_messages_never_count_as_unread_for_sender() -> None:
    c = Client()
    lara = c.user("lara", "Lara Lin")
    max_u = c.user("max", "Max Moss")
    nina = c.user("nina", "Nina Nunn")
    d = c.dm(lara, max_u)
    g = c.group(lara, [max_u, nina], "Team")
    c.send(lara, d, "my dm 1")
    c.send(lara, d, "my dm 2")
    c.send(lara, g, "my group 1")

    r_lara = c.get("/api/updates", user=lara)
    assert (r_lara.status, r_lara.json) == (
        200,
        {"unread_total": 0, "unread_conversations": 0, "friend_requests": 0},
    )

    r_max = c.get("/api/updates", user=max_u)
    assert (r_max.status, r_max.json) == (
        200,
        {"unread_total": 3, "unread_conversations": 2, "friend_requests": 0},
    )

    # When lara sends after receiving a message, post_message updates lara's last_read_id
    c.send(max_u, d, "reply from max")
    assert c.get("/api/updates", user=lara).json == {
        "unread_total": 1,
        "unread_conversations": 1,
        "friend_requests": 0,
    }
    c.send(lara, d, "lara replies back")
    assert c.get("/api/updates", user=lara).json == {
        "unread_total": 0,
        "unread_conversations": 0,
        "friend_requests": 0,
    }


def test_befriending_or_removing_request_updates_friend_requests_count() -> None:
    c = Client()
    lara = c.user("lara", "Lara Lin")
    pia = c.user("pia", "Pia Park")
    quin = c.user("quin", "Quin Quay")
    rex = c.user("rex", "Rex Roy")

    c.friend_request(pia, lara)
    c.friend_request(quin, lara)
    c.friend_request(lara, rex)

    assert c.get("/api/updates", user=lara).json == {
        "unread_total": 0,
        "unread_conversations": 0,
        "friend_requests": 2,
    }
    assert c.get("/api/updates", user=rex).json == {
        "unread_total": 0,
        "unread_conversations": 0,
        "friend_requests": 1,
    }

    c.befriend(lara, pia)
    assert c.get("/api/updates", user=lara).json == {
        "unread_total": 0,
        "unread_conversations": 0,
        "friend_requests": 1,
    }

    c.befriend(lara, quin)
    assert c.get("/api/updates", user=lara).json == {
        "unread_total": 0,
        "unread_conversations": 0,
        "friend_requests": 0,
    }


def test_updates_is_read_only() -> None:
    c = Client()
    lara = c.user("lara", "Lara Lin")
    max_u = c.user("max", "Max Moss")
    d = c.dm(lara, max_u)
    c.send(max_u, d, "unread msg")
    c.friend_request(max_u, lara)

    r1 = c.get("/api/updates", user=lara)
    r2 = c.get("/api/updates", user=lara)
    assert r1.status == 200
    assert r1.json == {"unread_total": 1, "unread_conversations": 1, "friend_requests": 1}
    assert r2.json == r1.json
    assert c.unread(lara, d) == 1


def test_lives_in_its_own_feature_folder() -> None:
    importlib.import_module("chatbook.features.updates.handler")
