"""Code to compute a schedule and dispatch tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import multiprocessing
import signal
import time
from typing import List, Tuple, Optional

from .util import ignore_signal


@dataclass(eq=True, frozen=True, order=True)
class Job:
    """A job to be executed on a recurring schedule."""
    seconds: int
    command: str


class Scheduler:
    """Schedule a collection of recurring jobs.

    Jobs are returned in order of scheduled execution time according to the
    defined delay and with respect to the time the scheduler was started. No
    special efforts are taken to provide high accuracy.
    """

    # When True, the scheduler sleep during iteration.
    sleep: bool

    log: Optional[logging.Logger]

    # List of jobs being scheduled.
    jobs: List[Job]

    # Timestamp the schedule was started.
    started: Optional[datetime]

    # Queue of tasks, sorted by datetime of next scheduled execution.
    schedule: List[Tuple[datetime, Job]]

    def __init__(
        self: Scheduler,
        sleep: bool = True,
        started: Optional[datetime] = None,
        log: Optional[logging.Logger] = None,
    ):
        """Initialise an empty, stopped scheduler."""
        self.jobs = []
        self.schedule = []
        self.sleep = sleep
        self.started = started
        self.log = log

    def __iter__(self):
        """Use the scheduler as an iterator over jobs."""
        # TODO: A better interface would untangle the default and as_from()
        # cases.
        return self.as_from(self.started or datetime.now())

    def as_from(self, now: datetime):
        """Return an iterator of job scheduled from now."""
        if self.log:
            self.log.info(f"Starting at {now} with {len(self.jobs)} jobs.")
        self.started = now
        self.schedule = sorted([
            (now + timedelta(seconds=j.seconds), j) for j in sorted(self.jobs)
        ])
        return self

    def __next__(self):
        """Return the next scheduled job."""
        if (not self.started) or len(self.schedule) == 0:
            raise StopIteration
        deadline, job = self.schedule[0]
        # TODO: Replace the sorted-array with a better data structure.
        self.schedule[0] = (deadline + timedelta(seconds=job.seconds), job)
        self.schedule.sort()
        sleep = (deadline - datetime.now()).total_seconds()
        if self.sleep and sleep > 0:
            if self.log:
                self.log.debug(f"Sleeping {sleep}s until next deadline.")
            time.sleep(sleep)
        return (deadline, job)

    def add_job(self, job: Job) -> None:
        """Add a Job to the schedule."""
        if self.started:
            raise ValueError("Cannot add job to running schedule.")
        self.jobs.append(job)


def scheduler(
    name: str,
    config: List[Tuple[int, str]],
    shutdown: multiprocessing.Value,
    request_queue: multiprocessing.Queue,
    verbose: bool
) -> None:
    """Execute the programme by enqueuing tasks at the appropriate time."""
    if verbose:
        logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(name)
    log.info(f"Starting process {name}.")

    # SIGINT will be delivered to the whole process group. We'll need to ignore
    # it in the worker processes to give them the opportunity to finish any
    # pending work.
    signal.signal(signal.SIGINT, ignore_signal(log))

    scheduler = Scheduler(sleep=True, log=log)
    for delay, url in config:
        scheduler.add_job(Job(seconds=delay, command=url))

    for ts, job in scheduler:
        if shutdown.value:
            break
        log.debug(f"Queuing task for {job.command} at {ts}")
        request_queue.put(job.command)
    log.info("Process scheduler-0 shutting down.")
