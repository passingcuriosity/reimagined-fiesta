"""Entrypoint for programme."""

import argparse
import functools
import itertools
import logging
from math import gcd
import multiprocessing
import queue
import signal
import time
from typing import List, Optional, Tuple


def ignore_signal(log):
    """Ignore a signal."""
    def ignore_signal(signum, frame):
        log.debug(f"Ignoring signal {signum}.")
    return ignore_signal


def worker(
    name: str,
    shutdown: multiprocessing.Value,
    request_queue: multiprocessing.Queue
) -> None:
    """Main loop for worker.
    
    This method is the entrypoint for the worker which executes the monitoring
    tasks. It is executed in a dedicate child process.
    """
    log = logging.getLogger(name)
    log.info(f"Starting process {name}.")

    # SIGINT will be delivered to the whole process group. We'll need to ignore
    # it in the worker processes to give them the opportunity to finish any
    # pending work.
    signal.signal(signal.SIGINT, ignore_signal(log))

    while not shutdown.value:
        try:
            req = request_queue.get(timeout=1)
            log.error(f"Process {name} processing {req}!")
            time.sleep(1)
        except queue.Empty:
            log.debug(f"No request to process.")
    # Flush any results that haven't been committed yet.
    log.warning(f"Process {name} shutting down.")


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
    dur = functools.reduce(lambda x, y: x * y // gcd(x,y), [s for s, _ in config])

    # Expand the configuration into a schedule for the full duration. All times
    # $t_{n}$ are relative to $t_{0}$.
    schedule = itertools.groupby(sorted([
        (n * s, url) for s, url in config for n in range(1, dur // s + 1)
    ]), lambda x: x[0])

    # Calculate a programme from the full schedule. All times $t_{n}$ are relative
    # to $t_{n-1}$.
    t = 0
    programme = []
    for s, urls in schedule:
        programme.append((s - t, [u for _, u in urls]))
        t = s

    return programme


def scheduler(
    programme: List[Tuple[int, List[str]]],
    shutdown: multiprocessing.Value,
    request_queue: multiprocessing.Queue
) -> None:
    """Queue requests to be executed."""
    log = logging.getLogger("scheduler")
    log.info("Starting scheduler")

    # SIGINT will be delivered to the whole process group. We'll need to ignore
    # it in the worker processes to give them the opportunity to finish any
    # pending work.
    signal.signal(signal.SIGINT, ignore_signal(log))

    for delay, urls in itertools.cycle(programme):
        log.warning(f"Sleeping for {delay}s before scheduling {len(urls)} tasks.")
        time.sleep(delay)
        if shutdown.value:
            break
        for url in urls:
            log.debug(f"Queuing task for {url}")
            request_queue.put(url)
    log.warning("Process scheduler-0 shutting down.")


def arg_parser() -> argparse.ArgumentParser:
    """Build a command-line argument parser for the program."""
    parser = argparse.ArgumentParser(description='Monitor URL request latency.')
    parser.add_argument('-W', '--workers', metavar='N', help='Number of workers', default=3, type=int)
    parser.add_argument('urls', metavar='FILE', help='File of URLs', type=argparse.FileType('r'))

    return parser


def parse_config_stream(file) -> Optional[List[Tuple[int, List[str]]]]:
    """Parse the application configuration from a file handle.
    
    The handle will be closed before the method returns.
    """
    with file as file:
        config = []
        for ln, line in enumerate(file.readlines()):
            line = line.strip()
            try:
                seconds, url = line.split(",", 2)
                config.append((int(seconds.strip()), url.strip()))
            except ValueError as exc:
                raise ValueError(f"Expected '<num>,<url>' on line {ln}: '{line}'") from exc
        return sorted(config)


def main():
    """Parse command-line arguments, start the program."""
    multiprocessing.set_start_method('forkserver')
    log = logging.getLogger("main")
    args = arg_parser().parse_args()

    config = parse_config_stream(args.urls)
    programme = compute_schedule(config)

    # Setup a shared variable and signal handler. When the main process receives
    # SIGINT it will set the variable and the various loops will exit at their
    # next opportunity.
    shutdown_flag = multiprocessing.Value('b', False)
    def shutdown(signum, frame):
        log.error(f"Shutdown initiated in response to signal {signum}.")
        shutdown_flag.value = True
    signal.signal(signal.SIGINT, shutdown)

    queue = multiprocessing.Queue(100)

    # Start the child processes to execute tasks.
    log.info(f"Starting {args.workers} worker process.")
    children = []
    for num in range(0, args.workers):
        p = multiprocessing.Process(target=worker, args=(f"worker-{num}", shutdown_flag, queue))
        children.append(p)
        p.start()

    # Start the scheduling loop in the main process.
    p = multiprocessing.Process(target=scheduler, args=(programme, shutdown_flag, queue))
    children.append(p)
    p.start()
    # scheduler(programme, shutdown_flag, queue)

    # The scheduler loop has terminated due to 
    for p in children:
        p.join()
    return 0
