"""Entrypoint for programme."""

import argparse
import logging
import multiprocessing
import signal
import sys
from datetime import timedelta
from typing import List, Optional, Tuple

from latency_logger import scheduler, worker


def arg_parser() -> argparse.ArgumentParser:
    """Build a command-line argument parser for the program."""
    parser = argparse.ArgumentParser(
        description='Monitor URL request latency.'
    )
    parser.add_argument(
        '-v', '--verbose', help='produce more verbose output',
        action='store_true', default=False
    )
    parser.add_argument(
        '-Q', '--queue', metavar='N', help='maximum queue length',
        type=int, default=100
    )
    parser.add_argument(
        '-W', '--workers', metavar='N', help='number of workers',
        type=int, default=3
    )
    parser.add_argument(
        '-B', '--bootstrap-servers', metavar="URLs", help="Kafka bootstrap servers",
        type=str, required=True
    )
    parser.add_argument(
        '-S', '--schema-registry', metavar='URL', help='schema registry URL',
        type=str, required=True
    )
    parser.add_argument(
        '--ca-cert', metavar="FILE", help="TLS CA certificate file for Kafka",
        type=str, default='ca.pem'
    )
    parser.add_argument(
        '--auth-cert', metavar="FILE", help="TLS client certificate file",
        type=str, default='service.cert'
    )
    parser.add_argument(
        '--auth-key', metavar="FILE", help="TLS client key file for",
        type=str, default='service.key'
    )
    parser.add_argument(
        '-T', '--topic', metavar='TOPIC', help='topic name',
        type=str, default='monitoring'
    )
    parser.add_argument(
        'urls', metavar='FILE', help='comma-separated file of delays (in seconds) and URLs',
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
                config.append((timedelta(seconds=int(seconds.strip())), url.strip()))
            except ValueError as exc:
                new_exc = ValueError(
                    f"Expected '<num>,<url>' on line {ln}: '{line}'"
                )
                raise new_exc from exc
        return sorted(config)


def main():
    """Parse command-line arguments, start the program."""
    args = arg_parser().parse_args()
    config = parse_config_stream(args.urls)

    if 'darwin' == sys.platform:
        # On MacOS Python builds is it not generally safe to fork() without
        # immediately exec()ing. This is moderately ludicrous but it is what
        # it is.
        #
        # TODO: I haven't checked but forkserver probably means the system
        # won't notice when children crash. This is bad.
        multiprocessing.set_start_method('forkserver')
    else:
        multiprocessing.set_start_method('fork')

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger("main")

    # Setup a shared variable and signal handler. When the main process
    # receives SIGINT it will set the variable and the various loops will exit
    # at their next opportunity.
    shutdown_flag = multiprocessing.Value('b', False)

    def shutdown(signum, frame):
        log.error(f"Shutdown initiated in response to signal {signum}.")
        shutdown_flag.value = True

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGCHLD, shutdown)

    queue = multiprocessing.Queue(args.queue)

    log.info(f"Starting {args.workers} worker process.")
    children = []

    scheduler_proc = multiprocessing.Process(
        target=scheduler.main,
        args=("scheduler-0", config, shutdown_flag, queue, args.verbose)
    )
    children.append(scheduler_proc)
    scheduler_proc.start()

    worker_config = worker.Config(
        topic=args.topic,
        schema_registry=args.schema_registry,
        bootstrap_servers=args.bootstrap_servers,
        verbose=args.verbose,
        ca_cert=args.ca_cert,
        auth_cert=args.auth_cert,
        auth_key=args.auth_key,
    )
    for num in range(0, args.workers):
        p = multiprocessing.Process(
            target=worker.main,
            args=(f"worker-{num}", shutdown_flag, queue, worker_config)
        )
        children.append(p)
        p.start()

    # TODO: Can we wait on them all? Or wait for SIGCHLD? If a child process
    # fails, we'll probably want to tear the world down.
    for p in children:
        p.join()

    return 0
