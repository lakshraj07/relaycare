"""Pure tests for the Fivetran MCP helpers (no server spawn).

The live MCP path (freshness read + targeted re-sync) is exercised via the loop
and the smoke test; here we cover the staleness math and the report formatting.
"""

from unravel import fivetran_mcp as ftm
from unravel.fivetran_mcp import FeedFreshness


def test_hours_since_parses_fivetran_timestamp():
    # a far-past timestamp should read as very old
    assert ftm._hours_since("2020-01-01T00:00:00.000000Z") > 1000
    assert ftm._hours_since(None) is None
    assert ftm._hours_since("not-a-date") is None


def test_feed_is_stale_threshold():
    fresh = FeedFreshness("gnomad", "id", "gcs", "scheduled", "x", hours_old=2.0)
    stale = FeedFreshness("clinvar", "id", "gcs", "scheduled", "x", hours_old=48.0)
    unknown = FeedFreshness("alphamissense", "id", "gcs", "scheduled", None, hours_old=None)
    assert not fresh.is_stale
    assert stale.is_stale
    assert unknown.is_stale  # unknown freshness is treated as stale (fail-safe)


def test_freshness_report_flags_stale():
    feeds = [
        FeedFreshness("clinvar", "a", "gcs", "scheduled", "x", 4.0),
        FeedFreshness("gnomad", "b", "gcs", "scheduled", "x", 50.0),
    ]
    report = ftm.freshness_report(feeds)
    assert "clinvar synced 4.0h ago" in report
    assert "gnomad synced 50.0h ago STALE" in report


def test_uvx_resolves_to_a_path():
    # in the venv, uvx is installed; the resolver should find it.
    assert ftm._uvx().endswith("uvx")
