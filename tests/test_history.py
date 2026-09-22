from datetime import datetime, timedelta, timezone

import pytest

import history
from history import History, filter_clips


class FakeClock:
    """Deterministic, strictly increasing UTC clock so ordering never depends on
    the OS timer resolution."""

    def __init__(self):
        self._t = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self, tz=None):
        self._t += timedelta(seconds=1)
        return self._t


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()

    class _DT:
        now = staticmethod(fake.now)

    monkeypatch.setattr(history, "datetime", _DT)
    return fake


@pytest.fixture
def hist(tmp_path, clock):
    h = History(db_path=tmp_path / "history.db", max_entries=500)
    yield h
    h._conn.close()


def texts(h, limit=1000):
    return [r["text"] for r in h.recent(limit)]


def test_add_and_recent_newest_first(hist):
    for t in ("one", "two", "three"):
        hist.add(t)
    assert texts(hist) == ["three", "two", "one"]


@pytest.mark.parametrize("blank", ["", "   ", "\n\t ", None])
def test_blank_text_is_ignored(hist, blank):
    hist.add(blank)
    assert hist.count() == 0


def test_duplicate_bumps_existing_entry_instead_of_inserting(hist):
    hist.add("a")
    hist.add("b")
    hist.add("c")
    hist.add("a")  # re-copy the oldest entry
    assert hist.count() == 3
    assert texts(hist) == ["a", "c", "b"]


def test_dedup_is_exact_match(hist):
    # Documented behaviour: a stray leading space counts as a different clip.
    hist.add("hello")
    hist.add(" hello")
    assert hist.count() == 2


def test_history_is_capped_and_oldest_are_dropped(tmp_path, clock):
    h = History(db_path=tmp_path / "cap.db", max_entries=5)
    for i in range(8):
        h.add(f"clip {i}")
    assert h.count() == 5
    assert texts(h) == [f"clip {i}" for i in (7, 6, 5, 4, 3)]
    h._conn.close()


def test_default_cap_is_500(tmp_path, clock):
    h = History(db_path=tmp_path / "cap500.db")
    assert h.max_entries == 500
    for i in range(505):
        h.add(f"clip {i}")
    assert h.count() == 500
    assert texts(h)[0] == "clip 504"
    assert "clip 4" not in texts(h)
    assert "clip 5" in texts(h)
    h._conn.close()


def test_bumped_entry_survives_the_cap(tmp_path, clock):
    h = History(db_path=tmp_path / "bump.db", max_entries=3)
    for t in ("a", "b", "c"):
        h.add(t)
    h.add("a")  # a is now the newest, b the oldest
    h.add("d")  # pushes out the oldest -> b
    assert sorted(texts(h)) == ["a", "c", "d"]
    h._conn.close()


def test_recent_respects_limit(hist):
    for i in range(10):
        hist.add(f"clip {i}")
    assert len(hist.recent(3)) == 3
    assert texts(hist, 3) == ["clip 9", "clip 8", "clip 7"]


def test_clear_empties_history(hist):
    hist.add("x")
    hist.clear()
    assert hist.count() == 0
    assert hist.recent() == []


def test_history_persists_across_reopen(tmp_path, clock):
    path = tmp_path / "persist.db"
    h1 = History(db_path=path)
    h1.add("kept")
    h1._conn.close()
    h2 = History(db_path=path)
    assert texts(h2) == ["kept"]
    h2._conn.close()


def test_unicode_and_multiline_roundtrip(hist):
    s = "line1\nline2 ☃ \U0001f600"
    hist.add(s)
    assert texts(hist) == [s]


def test_real_clock_rapid_adds_keep_the_newest(tmp_path):
    # No fake clock: adds in a tight loop must still evict the *oldest* rows.
    h = History(db_path=tmp_path / "real.db", max_entries=3)
    for i in range(20):
        h.add(f"clip {i}")
    assert h.count() == 3
    assert texts(h) == ["clip 19", "clip 18", "clip 17"]
    h._conn.close()


ITEMS = [
    {"text": "Hello World", "updated_at": "2026-01-01T00:00:00+00:00"},
    {"text": "hello again", "updated_at": "2026-01-01T00:00:01+00:00"},
    {"text": "Something ELSE", "updated_at": "2026-01-01T00:00:02+00:00"},
]


def test_search_is_case_insensitive_substring():
    assert [i["text"] for i in filter_clips(ITEMS, "HELLO")] == ["Hello World", "hello again"]
    assert [i["text"] for i in filter_clips(ITEMS, "else")] == ["Something ELSE"]


@pytest.mark.parametrize("query", ["", "   ", None])
def test_blank_search_returns_everything_in_order(query):
    assert filter_clips(ITEMS, query) == ITEMS


def test_search_query_is_stripped_and_no_match_is_empty():
    assert len(filter_clips(ITEMS, "  world  ")) == 1
    assert filter_clips(ITEMS, "zzz") == []
