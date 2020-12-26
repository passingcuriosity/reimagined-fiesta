Python Latency Logger
=====================

This is a toy program that periodically makes HTTP requests and records
the latency. It's mostly an experiment to let me try writing parallel
code in Python.

At some point, if I find the time, I'll try to compare `asyncio`,
`threading`, `multiprocessing`. For the time being, it uses
`multiprocessing`.

If running on MacOS, it's easiest to use a Python release with a Wheel
package of https://pypi.org/project/confluent-kafka/. I used Homebrew's
`python@3.8` formula.

Architecture
------------

The overall architecture attempts to 

The system is composed of three main components:

1. The main process handles the user interface.

2. The scheduler process dispatches tasks according to the schedule.

3. The worker processes execute the tasks.

There are two ways processes communicate:

- A shared variable is used by the main process to instruct children to
  shutdown.

- A shared queue of tasks is written by the scheduler and read by the
  workers.
