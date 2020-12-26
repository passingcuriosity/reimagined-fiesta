from itertools import groupby
from functools import reduce
from math import gcd

from latency_logger import compute_schedule


def test_singleton_empty():
    """Test that an empty config generates an empty programme."""

    config = []

    programme = compute_schedule(config)

    assert programme == []


def test_singleton_programme():
    """Test that a single record generates a valid programme."""

    config = [(10, "https://example.com/")]

    programme = compute_schedule(config)

    assert programme == [(10, ["https://example.com/"])]


def test_programme():
    """Test computing the programme against a small example."""

    config = [
        (2, "http://2.s.com/"),
        (4, "http://4.s.com/"),
        (5, "http://5.s.com/"),
    ]

    programme = compute_schedule(config)

    assert programme == [
        (2, ['http://2.s.com/']),
        (2, ['http://2.s.com/', 'http://4.s.com/']),
        (1, ['http://5.s.com/']),
        (1, ['http://2.s.com/']),
        (2, ['http://2.s.com/', 'http://4.s.com/']),
        (2, ['http://2.s.com/', 'http://5.s.com/']),
        (2, ['http://2.s.com/', 'http://4.s.com/']),
        (2, ['http://2.s.com/']),
        (1, ['http://5.s.com/']),
        (1, ['http://2.s.com/', 'http://4.s.com/']),
        (2, ['http://2.s.com/']),
        (2, ['http://2.s.com/', 'http://4.s.com/', 'http://5.s.com/']),
    ]


