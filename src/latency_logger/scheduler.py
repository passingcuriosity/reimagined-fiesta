"""Code to compute a schedule and dispatch tasks."""

import functools
import itertools
import logging
from math import gcd
import multiprocessing
import signal
import time
from typing import List, Tuple

from .util import ignore_signal


def compute_schedule(
    config: List[Tuple[int, str]]
) -> List[Tuple[int, List[str]]]:
    """Compute the programme of requests.

    This method returns a list of tuples of a delay (in seconds) and a list of
    URLs to dispatch. The returned list can be cycled to obtain the appropriate
    behaviour.
    """
    # Find the duration of the programme. This is the LCM of the durations of
    # each step.
    durations = [s for s, _ in config]
    dur = functools.reduce(lambda x, y: x * y // gcd(x, y), durations)

    # Expand the configuration into a schedule for the full duration. All times
    # $t_{n}$ are relative to $t_{0}$.
    schedule = itertools.groupby(sorted([
        (n * s, url) for s, url in config for n in range(1, dur // s + 1)
    ]), lambda x: x[0])

    # Calculate a programme from the full schedule. All times $t_{n}$ are
    # relative to $t_{n-1}$.
    t = 0
    programme = []
    for s, urls in schedule:
        programme.append((s - t, [u for _, u in urls]))
        t = s

    return programme


def scheduler(
    name: str,
    programme: List[Tuple[int, List[str]]],
    shutdown: multiprocessing.Value,
    request_queue: multiprocessing.Queue
) -> None:
    """Execute the programme by enqueuing tasks at the appropriate time."""
    log = logging.getLogger(name)
    log.info(f"Starting process {name}.")

    # SIGINT will be delivered to the whole process group. We'll need to ignore
    # it in the worker processes to give them the opportunity to finish any
    # pending work.
    signal.signal(signal.SIGINT, ignore_signal(log))

    for delay, urls in itertools.cycle(programme):
        log.debug(f"Sleeping for {delay} before scheduling {len(urls)} tasks.")
        time.sleep(delay)
        if shutdown.value:
            break
        for url in urls:
            log.debug(f"Queuing task for {url}")
            request_queue.put(url)
    log.warning("Process scheduler-0 shutting down.")
