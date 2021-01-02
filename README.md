Python Latency Logger
=====================

This is a toy program that periodically makes HTTP requests and records the
latency. It's mostly an experiment to let me try writing concurrent code in
Python. At some point, if I find the time, I'll try to compare `asyncio`,
`threading`, `multiprocessing`. For the time being, it uses `multiprocessing`.

The real work -- making the requests and writing the results to Kafka -- is
done with third-party libraries:

- [PycURL](https://pypi.org/project/pycurl/)
- [Confluent Kafka](https://pypi.org/project/confluent-kafka/)

These are both Python wrappers around C libraries. If you choose your OS and
Python release carefully, there are binary Wheels available with the libraries
built-in.

Usage
-----

```
latency-logger [-h] [-v] [-Q N] [-W N] FILE

Monitor URL request latency.

positional arguments:
  FILE               comma-separated file of delays (in seconds) and URLs

optional arguments:
  -h, --help         show this help message and exit
  -v, --verbose      produce more verbose output
  -Q N, --queue N    maximum queue length
  -W N, --workers N  number of workers
```

Development
-----------

```
$ [ -f venv/bin/activate ] || python3 -m venv venv
$ . venv/bin/activate
(venv) $ export PYCURL_SSL_LIBRARY=openssl
(venv) $ pip install -e .[dev]
(venv) $ flake8 *.py src/ test/
(venv) $ pytest -vv
(venv) $ latency-logger --verbose demo.csv
```

Architecture
------------

The system is composed of three main components:

1. The main process spawns the workers, receives and handles signals, etc.

2. The scheduler process maintains the schedule and enqueues tasks for
   processing.

3. The worker processes dequeue tasks and process them, using PycURL to perform
   the requests and Confluent's Kafka client library to publish the results.

There are two ways processes communicate:

- A shared variable is used by the main process to instruct children to
  shutdown. This is set in signal handlers for SIGINT and SIGTERM.

- A shared queue of tasks is written by the scheduler and read by the
  workers.

## Main

The main process handles the command-line arguments, reads the configuration
file, creates the IPC channels, and launches the child processes.

As part of its initialisation, the main process register a signal handler for
`SIGINT`, `SIGTERM`, and `SIGCHLD`. When any of these signals are received,
shared variable is set and the children should terminate gracefully.

Once the system has started running the main process waits for the children to
terminate.

## Scheduler

A simple scheduler is used to maintain a queue of jobs ordered by their next
execution time. The code is extremely naive -- a sorted array, resorted when
changes are made -- and could easily be replaced with a heap to improve the
asymptotics for large collections of sites to monitor.

## Worker

The worker processes start a Kafka producer (configure to serialise messages to
Avro) and then start their processing loop. In each iteration, they poll the
Kafka client to process any pending events (e.g. logging Kafka errors to the
worker process output), fetch a pending task from the queue, run the request,
and write the results to Kafka.

The exception handling is currently MIA.

## Caveats

This whole assembly more or less assumes deployment on a POSIX-ish system doing
normal POSIX-y things. Like forking, handling signals, etc.

Importantly, the problems around fork() on MacOS makes some problems more
problematic. On platforms where it uses `fork`, the main process should notice
when children die and terminate the system saftely. Unless `forkserver` is
doing something clever under the covers (🤞) and forwarding `SIGCHLD` then we're
probably out of luck in that regard.

Deployment
----------

