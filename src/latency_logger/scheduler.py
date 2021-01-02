"""Code to compute a schedule and dispatch tasks."""

from __future__ import annotations

import logging
import multiprocessing
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator, List, Optional, Tuple


@dataclass(eq=True, frozen=True, order=True)
class Job:
    """A job to be executed on a recurring schedule."""

    delay: timedelta
    command: str


class ScheduleIterator:
    """An iterator over jobs scheduled from a starting datetime."""

    sleep: bool
    started: datetime
    schedule: List[Tuple[datetime, Job]]
    log: Optional[logging.Logger]

    def __init__(
        self: ScheduleIterator,
        sleep: bool,
        started: datetime,
        jobs: List[Job],
        log: Optional[logging.Logger] = None,
    ) -> None:
        """Build a schedule for the datetime and jobs."""
        if len(jobs) == 0:
            raise ValueError("Cannot run with empty schedule.")
        self.sleep = sleep
        self.log = log
        self.started = started
        self.schedule = sorted([(started + j.delay, j) for j in jobs])
        if self.log:
            self.log.info(f"Starting at {started} with {len(jobs)} jobs.")

    def __iter__(self: ScheduleIterator) -> Iterator[Job]:
        """Return self as iterator."""
        return self

    def __next__(self: ScheduleIterator) -> Tuple[datetime, Job]:
        """Return the next scheduled deadline and job.

        This method will sleep if the instance was instantiated with sleep=True.
        """
        if (self.started is None) or len(self.schedule) == 0:
            raise StopIteration
        deadline, job = self.schedule[0]
        # TODO: Replace the sorted-array with a better data structure.
        self.schedule[0] = (deadline + job.delay, job)
        self.schedule.sort()
        sleep = (deadline - datetime.now()).total_seconds()
        if self.sleep and sleep > 0:
            if self.log:
                self.log.debug(f"Sleeping {sleep}s until next deadline.")
            time.sleep(sleep)
        return (deadline, job)


class Scheduler:
    """Schedule a collection of recurring jobs.

    Jobs are returned in order of scheduled execution time according to the
    defined delay and with respect to the time the scheduler was started. No
    special efforts are taken to provide high accuracy.
    """

    sleep: bool

    log: Optional[logging.Logger]

    jobs: List[Job]

    def __init__(
        self: Scheduler,
        sleep: bool = True,
        log: Optional[logging.Logger] = None,
    ) -> Scheduler:
        """Initialise an empty, stopped scheduler."""
        self.jobs = []
        self.sleep = sleep
        self.log = log

    def __iter__(self: Scheduler) -> Iterator[Job]:
        """Iterate over the jobs scheduled from now."""
        return self.as_from(datetime.now())

    def as_from(self: Scheduler, now: datetime) -> Iterator[Job]:
        """Return an iterator of job executions scheduled from the give datetime."""
        return ScheduleIterator(self.sleep, now, self.jobs)

    def add_job(self: Scheduler, job: Job) -> None:
        """Add a Job to the schedule."""
        self.jobs.append(job)


def main(
    name: str,
    config: List[Tuple[timedelta, str]],
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
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    scheduler = Scheduler(sleep=True, log=log)
    for delay, url in config:
        scheduler.add_job(Job(delay=delay, command=url))

    for ts, job in scheduler:
        if shutdown.value:
            break
        log.debug(f"Queuing task for {job.command} at {ts}")
        request_queue.put(job.command)
    log.info("Process scheduler-0 shutting down.")
