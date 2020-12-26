"""Entrypoint for programme."""

import argparse
import logging
import multiprocessing
import signal
from typing import List, Optional, Tuple


from .scheduler import compute_schedule, scheduler
from .worker import worker


def arg_parser() -> argparse.ArgumentParser:
    """Build a command-line argument parser for the program."""
    parser = argparse.ArgumentParser(
        description='Monitor URL request latency.'
    )
    parser.add_argument(
        '-Q', '--queue', metavar='N', help='Maximum queue length',
        type=int, default=100
    )
    parser.add_argument(
        '-W', '--workers', metavar='N', help='Number of workers',
        type=int, default=3
    )
    parser.add_argument(
        'urls', metavar='FILE', help='File of URLs',
        type=argparse.FileType('r')
    )

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
                new_exc = ValueError(
                    f"Expected '<num>,<url>' on line {ln}: '{line}'"
                )
                raise new_exc from exc
        return sorted(config)


def main():
    """Parse command-line arguments, start the program."""
    multiprocessing.set_start_method('forkserver')
    log = logging.getLogger("main")

    # Setup a shared variable and signal handler. When the main process
    # receives SIGINT it will set the variable and the various loops will exit
    # at their next opportunity.
    shutdown_flag = multiprocessing.Value('b', False)

    def shutdown(signum, frame):
        log.error(f"Shutdown initiated in response to signal {signum}.")
        shutdown_flag.value = True

    signal.signal(signal.SIGINT, shutdown)

    args = arg_parser().parse_args()
    config = parse_config_stream(args.urls)
    programme = compute_schedule(config)

    # Create a work queue.
    queue = multiprocessing.Queue(args.queue)

    # Start the child processes.
    log.info(f"Starting {args.workers} worker process.")
    children = []

    # The scheduler process.
    p = multiprocessing.Process(
        target=scheduler,
        args=("scheduler-0", programme, shutdown_flag, queue)
    )
    children.append(p)
    p.start()

    for num in range(0, args.workers):
        p = multiprocessing.Process(
            target=worker,
            args=(f"worker-{num}", shutdown_flag, queue)
        )
        children.append(p)
        p.start()

    # TODO: Can we wait on them all? Or wait for SIGCHLD? If a child process
    # fails, we'll probably want to tear the world down.
    for p in children:
        p.join()

    return 0
