from datetime import datetime, timedelta, timezone

from popup import _preview, _relative_time


def _ago(**kw):
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat()


def test_relative_time_buckets():
    assert _relative_time(_ago(seconds=5)) == "just now"
    assert _relative_time(_ago(minutes=5, seconds=1)) == "5m ago"
    assert _relative_time(_ago(hours=3, seconds=1)) == "3h ago"
    assert _relative_time(_ago(days=2, seconds=1)) == "2d ago"


def test_relative_time_bad_input_is_blank():
    assert _relative_time("not a date") == ""
    assert _relative_time(None) == ""


def test_preview_collapses_whitespace_and_truncates():
    assert _preview("a\n\n  b\tc") == "a b c"
    long = "x" * 200
    out = _preview(long, limit=10)
    assert out == "x" * 10 + "…"
