"""Code to execute tasks."""

import logging
import multiprocessing
import queue
import signal

import pycurl


def worker(
    name: str,
    shutdown: multiprocessing.Value,
    request_queue: multiprocessing.Queue,
    verbose: bool
) -> None:
    """Main loop for worker.

    This method is the entrypoint for the worker which executes the monitoring
    tasks. It is executed in a dedicate child process.
    """
    if verbose:
        logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(name)
    log.info(f"Starting process {name}.")

    # SIGINT will be delivered to the whole process group. We'll need to ignore
    # it in the worker processes to give them the opportunity to finish any
    # pending work.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    while not shutdown.value:
        try:
            req = request_queue.get(timeout=1)
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, req)
            curl.setopt(pycurl.CONNECTTIMEOUT, 30)
            curl.setopt(pycurl.TIMEOUT, 300)
            curl.setopt(pycurl.NOSIGNAL, 1)
            curl.setopt(pycurl.WRITEFUNCTION, lambda b: len(b))
            try:
                curl.perform()
                code = curl.getinfo(pycurl.RESPONSE_CODE)
                ts = {
                    'dns': curl.getinfo(pycurl.NAMELOOKUP_TIME),
                    'tcp': curl.getinfo(pycurl.CONNECT_TIME),
                    'ssl': curl.getinfo(pycurl.APPCONNECT_TIME),
                    'req': curl.getinfo(pycurl.STARTTRANSFER_TIME),
                    'fin': curl.getinfo(pycurl.TOTAL_TIME),
                }
                print(f"{req} ({code}): {ts}")
            except:
                raise
            curl.close()
        except queue.Empty:
            log.debug("No request to process.")
    # Flush any results that haven't been committed yet.
    log.warning(f"Process {name} shutting down.")
