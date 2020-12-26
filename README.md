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

A configuration file is read at startup which describes the URLs to be
monitored and the frequency with which they should each be checked.

Then a multiprocessing queue is initialised and a number of workers are
forked to actually perform the checks.
