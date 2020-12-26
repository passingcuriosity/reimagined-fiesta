"""Utility functions."""


def ignore_signal(log):
    """Return a signal handler that ignores the signal."""
    def ignore_signal(signum, frame):
        log.debug(f"Ignoring signal {signum}.")
    return ignore_signal
