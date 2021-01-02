"""Tests for the worker functionality."""

from datetime import datetime, timedelta
from queue import Queue

import pycurl
import pytest

from latency_logger import worker


CONFIG = worker.Config(
    topic="test-topic",
    schema_registry="https://schema-registry/",
    bootstrap_servers="127.0.0.1:9090,127.0.0.1:9091",
    ca_cert="/tmp/ca.pem",
    auth_key="/tmp/service.key",
    auth_cert="/tmp/service.cert"
)


class MockTerminationVariable:
    """Mock variable to signal termination after |n| inspections."""
    def __init__(self, terminate_on: int):
        self.count = terminate_on
        self.reads = 0

    @property
    def value(self):
        self.reads += 1
        return int(not max(0, self.count - self.reads))


@pytest.fixture
def mock_curl(mocker):
    """Mock [some] PycURL methods."""
    curl_class = mocker.patch('pycurl.Curl', autospec=True)
    curl = curl_class.return_value
    curl.setopt.return_value = None
    curl.perform.return_value = None

    n = 0

    def fake_info(info, **kwargs):
        nonlocal n
        n += 1
        if info == pycurl.RESPONSE_CODE:
            return n
        if info == pycurl.NAMELOOKUP_TIME:
            return n
        if info == pycurl.CONNECT_TIME:
            return n
        if info == pycurl.APPCONNECT_TIME:
            return n
        if info == pycurl.PRETRANSFER_TIME:
            return n
        if info == pycurl.STARTTRANSFER_TIME:
            return n
        if info == pycurl.TOTAL_TIME:
            return n
        return None

    curl.getinfo = fake_info

    return curl


@pytest.fixture
def mock_producer(mocker):
    """Mock the Kafka producer classes used in worker."""
    mocker.patch('latency_logger.worker.SchemaRegistryClient', autospec=True)
    mocker.patch('latency_logger.worker.AvroSerializer', autospec=True)
    mocker.patch('latency_logger.worker.StringSerializer', autospec=True)

    producer_class = mocker.patch('latency_logger.worker.SerializingProducer', autospec=True)
    producer = producer_class.return_value
    producer.poll.return_value = None
    producer.produce.return_value = None

    return producer


@pytest.fixture
def mock_datetime(mocker):
    """Mock datetime.datetime.now in worker."""
    start_time = datetime.now()
    fake_time = start_time

    def now():
        nonlocal fake_time
        fake_time += timedelta(seconds=1)
        return fake_time

    mock_cls = mocker.patch('latency_logger.worker.datetime', autospec=True)
    mock_cls.now = now

    mock_inst = mock_cls.return_value
    mock_inst.start_time = start_time

    return mock_inst


def test_mock_termination_variable():
    """Test that the mock termination variable works."""
    terminate = MockTerminationVariable(terminate_on=3)
    assert terminate.value == 0
    assert terminate.value == 0
    assert terminate.value == 1
    assert terminate.value == 1


def test_worker(mocker, mock_curl, mock_producer, mock_datetime):
    """Test that the worker performs requests."""

    number_to_process = 3
    urls = [f"https://localhost/{n}" for n in range(0, number_to_process + 2)]

    queue = Queue()
    for u in urls:
        queue.put(u)
    term = MockTerminationVariable(terminate_on=number_to_process + 1)
    worker.main("test-worker", term, queue, CONFIG)

    assert term.reads == number_to_process + 1

    assert len(mock_curl.perform.call_args_list) == number_to_process

    actual_urls_requested = [
        c.args[1] for c in mock_curl.setopt.call_args_list if c.args[0] == pycurl.URL
    ]
    assert actual_urls_requested == urls[0:number_to_process]

    assert len(mock_producer.poll.call_args_list) == number_to_process

    ts = mock_datetime.start_time.timestamp()

    def expected_report(n):
        nonlocal ts
        t = n * 7
        return (
            f"https://localhost/{n}",
            worker.Report(
                url=f"https://localhost/{n}",
                code=t + 1,
                timestamp=ts + n + 1,
                namelookup=t + 2,
                connect=t + 3,
                appconnect=t + 4,
                pretransfer=t + 5,
                starttransfer=t + 6,
                total=t + 7
            )
        )

    actual_produced_records = [
        (c.kwargs['key'], c.kwargs['value']) for c in mock_producer.produce.call_args_list
    ]
    assert actual_produced_records == [expected_report(n) for n in range(0, number_to_process)]


def test_worker_handles_failing_requests():
    """Test that the worker correctly handles failing URLs."""
    pytest.skip("Not implemented")


def test_worker_recovers_from_kafka_failures():
    """Test that the worker recovers from non-fatal Kafka errors."""
    pytest.skip("Not implemented")
