"""Code to execute tasks."""

import logging
import multiprocessing
import queue
import signal

from .util import ignore_signal


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
        except queue.Empty:
            log.debug("No request to process.")
    # Flush any results that haven't been committed yet.
    log.warning(f"Process {name} shutting down.")
