"""Validators (core/validate.py): every row of DESIGN 3.7. Only status codes are asserted."""

from collections.abc import Callable
from typing import Any

import pytest

from chatbook.core.http import HTTPError, Request
from chatbook.core.store import connect
from chatbook.core.validate import (
    body_id,
    body_ids,
    body_str,
    path_id,
    query_int,
    query_opt_int,
    query_str,
)

DB = connect(":memory:", hash_iterations=1)


def req(
    body: object = None,
    *,
    params: dict[str, str] | None = None,
    query: dict[str, str] | None = None,
) -> Request:
    return Request(
        method="POST",
        path="/api/x",
        params=params or {},
        query=query or {},
        body=body,
        headers={},
        user=None,
        token=None,
        db=DB,
        now=0,
    )


def status(call: Callable[[], Any]) -> int:
    with pytest.raises(HTTPError) as info:
        call()
    return info.value.status


# --- body_str ---------------------------------------------------------------------------


def test_body_str_strips_by_default() -> None:
    assert body_str(req({"name": "  Ann  "}), "name") == "Ann"
    assert body_str(req({"name": "x" * 1000}), "name") == "x" * 1000


def test_body_str_bounds_apply_after_strip() -> None:
    assert body_str(req({"t": " abc "}), "t", max_len=3) == "abc"
    assert status(lambda: body_str(req({"t": "abcd"}), "t", max_len=3)) == 400
    assert status(lambda: body_str(req({"t": "   "}), "t")) == 400
    assert status(lambda: body_str(req({"t": ""}), "t")) == 400
    assert status(lambda: body_str(req({"t": "x" * 1001}), "t")) == 400
    assert status(lambda: body_str(req({"t": "abc"}), "t", min_len=4)) == 400


def test_body_str_without_strip_keeps_spaces() -> None:
    assert body_str(req({"p": " pw "}), "p", strip=False) == " pw "
    assert status(lambda: body_str(req({"p": " pw "}), "p", max_len=3, strip=False)) == 400


def test_body_str_min_len_zero_allows_empty() -> None:
    assert body_str(req({"bio": ""}), "bio", min_len=0) == ""
    assert body_str(req({"bio": "  "}), "bio", min_len=0) == ""


@pytest.mark.parametrize("body", [None, ["name"], "name", 5, {"other": "x"}, {"name": 5}])
def test_body_str_rejects_bad_bodies(body: object) -> None:
    assert status(lambda: body_str(req(body), "name")) == 400


@pytest.mark.parametrize("value", [None, True, 12, ["a"], {"a": 1}])
def test_body_str_rejects_non_strings(value: object) -> None:
    assert status(lambda: body_str(req({"name": value}), "name")) == 400


# --- body_id ----------------------------------------------------------------------------


def test_body_id_accepts_positive_ints() -> None:
    assert body_id(req({"user_id": 7}), "user_id") == 7
    assert body_id(req({"user_id": 10**15}), "user_id") == 10**15


@pytest.mark.parametrize("value", [0, -1, True, False, "7", 1.0, None, [7]])
def test_body_id_rejects(value: object) -> None:
    assert status(lambda: body_id(req({"user_id": value}), "user_id")) == 400


@pytest.mark.parametrize("body", [None, [7], 7, {}])
def test_body_id_rejects_bad_bodies(body: object) -> None:
    assert status(lambda: body_id(req(body), "user_id")) == 400


# --- body_ids ---------------------------------------------------------------------------


def test_body_ids_dedupes_in_first_seen_order() -> None:
    assert body_ids(req({"ids": [3, 1, 3, 2, 1]}), "ids") == [3, 1, 2]
    assert body_ids(req({"ids": []}), "ids") == []
    assert body_ids(req({"ids": list(range(1, 101))}), "ids") == list(range(1, 101))
    assert body_ids(req({"ids": [5, 6]}), "ids", max_items=2) == [5, 6]


@pytest.mark.parametrize(
    "value",
    [[0], [-2], [True], ["1"], [1.0], [None], [[1]], "1,2", 3, None, {"1": 1}],
)
def test_body_ids_rejects(value: object) -> None:
    assert status(lambda: body_ids(req({"ids": value}), "ids")) == 400


def test_body_ids_limits_the_number_of_items() -> None:
    assert status(lambda: body_ids(req({"ids": list(range(1, 102))}), "ids")) == 400
    assert status(lambda: body_ids(req({"ids": [1, 2, 3]}), "ids", max_items=2)) == 400


@pytest.mark.parametrize("body", [None, [1], {}])
def test_body_ids_rejects_bad_bodies(body: object) -> None:
    assert status(lambda: body_ids(req(body), "ids")) == 400


# --- path_id ----------------------------------------------------------------------------


def test_path_id_reads_digits() -> None:
    assert path_id(req(params={"id": "7"})) == 7
    assert path_id(req(params={"id": "007"})) == 7
    assert path_id(req(params={"id": "9" * 18})) == int("9" * 18)
    assert path_id(req(params={"id": "1", "uid": "42"}), "uid") == 42


@pytest.mark.parametrize("value", ["0", "000", "-1", "+1", "abc", "", "1.5", " 1", "1 ", "9" * 19])
def test_path_id_rejects_with_404(value: str) -> None:
    assert status(lambda: path_id(req(params={"id": value}))) == 404


def test_path_id_rejects_non_ascii_digits_and_missing_names() -> None:
    assert status(lambda: path_id(req(params={"id": "\uff11"}))) == 404  # fullwidth one
    assert status(lambda: path_id(req(params={"id": "\u0663"}))) == 404  # arabic-indic three
    assert status(lambda: path_id(req(params={}))) == 404
    assert status(lambda: path_id(req(params={"id": "4"}), "uid")) == 404


# --- query_str --------------------------------------------------------------------------


def test_query_str_strips_and_checks_length() -> None:
    assert query_str(req(query={"q": "  bo "}), "q", max_len=50) == "bo"
    assert query_str(req(query={"q": "x" * 50}), "q", max_len=50) == "x" * 50
    assert status(lambda: query_str(req(query={"q": "x" * 51}), "q", max_len=50)) == 400
    assert status(lambda: query_str(req(query={"q": "   "}), "q", max_len=50)) == 400
    assert status(lambda: query_str(req(), "q", max_len=50)) == 400
    assert status(lambda: query_str(req(query={"q": "ab"}), "q", max_len=5, min_len=3)) == 400


def test_query_str_min_len_zero_allows_missing() -> None:
    assert query_str(req(), "q", max_len=5, min_len=0) == ""


# --- query_int --------------------------------------------------------------------------


def test_query_int_defaults_and_bounds() -> None:
    assert query_int(req(), "limit", default=20, lo=1, hi=50) == 20
    assert query_int(req(query={"limit": ""}), "limit", default=20, lo=1, hi=50) == 20
    assert query_int(req(query={"limit": "1"}), "limit", default=20, lo=1, hi=50) == 1
    assert query_int(req(query={"limit": "50"}), "limit", default=20, lo=1, hi=50) == 50
    assert query_int(req(query={"n": "-3"}), "n", default=0, lo=-5, hi=5) == -3


@pytest.mark.parametrize("value", ["0", "51", "-1", "abc", "1.5", "1e3", "+5", "9" * 19, "\uff15"])
def test_query_int_rejects(value: str) -> None:
    def call() -> int:
        return query_int(req(query={"limit": value}), "limit", default=20, lo=1, hi=50)

    assert status(call) == 400


# --- query_opt_int ----------------------------------------------------------------------


def test_query_opt_int() -> None:
    assert query_opt_int(req(), "before") is None
    assert query_opt_int(req(query={"before": ""}), "before") is None
    assert query_opt_int(req(query={"before": "0"}), "before") == 0
    assert query_opt_int(req(query={"before": "12"}), "before") == 12


@pytest.mark.parametrize("value", ["-1", "x", "1.5", "9" * 19, "+1", "\uff11"])
def test_query_opt_int_rejects(value: str) -> None:
    assert status(lambda: query_opt_int(req(query={"before": value}), "before")) == 400
