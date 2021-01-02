"""Unit tests for the scheduling code."""

from datetime import datetime, timedelta
from itertools import islice, takewhile
from typing import List

import hypothesis.strategies as st
import pytest
from hypothesis import given

from latency_logger.scheduler import Job, Scheduler


NOW = datetime(2021, 1, 2, 15, 18, 21)


def test_empty_programme() -> None:
    """Test that an empty configuration reports an error."""
    s = Scheduler(sleep=False)

    with pytest.raises(ValueError) as exc_info:
        list(islice(s.as_from(NOW), 0, 10))
    assert "empty schedule" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        list(islice(s, 0, 10))
    assert "empty schedule" in str(exc_info.value)


def test_singleton_programme() -> None:
    """Test that a single record config a valid programme."""
    config = [(timedelta(seconds=10), "https://example.com/")]

    s = Scheduler(sleep=False)
    for d, u in config:
        s.add_job(Job(d, u))

    programme = list(islice(s.as_from(NOW), 0, 5))

    t10 = programme[-1][0]
    assert (t10 - NOW) == timedelta(seconds=50)


def test_canned_programme() -> None:
    """Test computing the programme from a small configuration."""
    config = [
        (timedelta(seconds=4), "http://4.s.com/"),
        (timedelta(seconds=2), "http://2.s.com/"),
        (timedelta(seconds=5), "http://5.s.com/"),
    ]

    s = Scheduler(sleep=False)
    for d, u in config:
        s.add_job(Job(d, u))

    programme = list(islice(s.as_from(NOW), 0, 19))

    t_n = programme[-1][0]
    assert (t_n - NOW) == timedelta(seconds=20)

    assert [j.command for d, j in programme] == [
        # 2
        "http://2.s.com/",
        # 4
        "http://2.s.com/",
        "http://4.s.com/",
        # 5
        "http://5.s.com/",
        # 6
        "http://2.s.com/",
        # 8
        "http://2.s.com/",
        "http://4.s.com/",
        # 10
        "http://2.s.com/",
        "http://5.s.com/",
        # 12
        "http://2.s.com/",
        "http://4.s.com/",
        # 14
        "http://2.s.com/",
        # 15
        "http://5.s.com/",
        # 16
        "http://2.s.com/",
        "http://4.s.com/",
        # 18
        "http://2.s.com/",
        # 20
        "http://2.s.com/",
        "http://4.s.com/",
        "http://5.s.com/",
    ]


@given(st.lists(
    st.integers(min_value=1, max_value=60*60),
    min_size=1,
    max_size=10
))
def test_programme_invariants(times: List[int]) -> None:
    """Test schedule invariants against random configurations."""
    # We'll validate a duration long enough to see every task twice.
    d = 2 * max(times)
    config = [
        (delay, f"http://www.{ix}.org/") for ix, delay in enumerate(times)
    ]

    inspect_n = 0
    s = Scheduler(sleep=False)
    for ts, url in config:
        s.add_job(Job(timedelta(seconds=ts), url))
        inspect_n += d // ts

    end = NOW + timedelta(seconds=d)
    programme = list(takewhile(lambda v: v[0] <= end, s.as_from(NOW)))
    assert len(programme) == inspect_n, f"Expected {inspect_n} tasks."

    # Each task is executed the expected number of times.
    for n, url in config:
        expected = d // n
        actual = len([
            1 for _, job in programme if job.command == url
        ])
        assert actual == expected, f"Should schedule {url} {expected} times."

    reqs = []
    for n, url in sorted(config):
        reqs += [
            (ts, url) for ts in range(0, d + 1, n)[1:]
        ]
    # Pretty sure we're relying on sorted being stable here?
    expected = [url for _, url in sorted(reqs, key=lambda x: x[0])]
    actual = [job.command for _, job in programme]
    # TODO: A more precise test would check that the actual schedule is in the
    # equivalence class up to reordering the tasks within each second.
    assert actual == expected, "Scheduled tasks should be in expected order."
