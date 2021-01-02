"""Tests for the worker functionality."""

from datetime import datetime, timedelta
from queue import Queue
from unittest.mock import call

import confluent_kafka
import confluent_kafka.serialization
import confluent_kafka.schema_registry
import confluent_kafka.schema_registry.avro
import pycurl
import pytest
from pytest_mock import MockerFixture

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


def test_mock_termination_variable():
    """Test that the mock termination variable works"""
    terminate = MockTerminationVariable(terminate_on=3)
    assert terminate.value == 0
    assert terminate.value == 0
    assert terminate.value == 1
    assert terminate.value == 1


class Mock:
    def __init__(self, *args, **kwargs):
        raise ValueError("ERROR")

def test_worker(mocker: MockerFixture, class_mocker):
    """Test that the worker performs requests."""

    number_to_process = 3
    urls = [f"https://localhost/{n + 1}" for n in range(0, number_to_process + 2)]

    start_time = datetime.now()
    def fake_clock(start_time):
        fake_time = start_time
        def now():
            nonlocal fake_time
            fake_time += timedelta(seconds=1)
            return fake_time
        return now

    mock_datetime_class = class_mocker.patch('latency_logger.worker.datetime', autospec=True)
    mock_datetime_class.now = fake_clock(start_time)
    mock_datetime = mock_datetime_class.return_value

    class_mocker.patch('latency_logger.worker.SchemaRegistryClient', autospec=True)
    class_mocker.patch('latency_logger.worker.AvroSerializer', autospec=True)
    class_mocker.patch('latency_logger.worker.StringSerializer', autospec=True)
    
    producer_class = class_mocker.patch('latency_logger.worker.SerializingProducer', autospec=True)
    producer = producer_class.return_value
    producer.poll.return_value = None
    producer.produce.return_value = None

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
        return "wot"
    curl.getinfo = fake_info

    queue = Queue()
    for u in urls:
        queue.put(u)
    term = MockTerminationVariable(terminate_on=number_to_process + 1)

    worker.main("test-worker", term, queue, CONFIG)

    assert term.reads == number_to_process + 1

    # Verify calls to cURL methods.
    actual_requests_processed = len(curl.perform.call_args_list)
    assert actual_requests_processed == number_to_process
    actual_urls_requested = [kall.args[1] for kall in curl.setopt.call_args_list if kall.args[0] == pycurl.URL]
    assert actual_urls_requested == urls[0:number_to_process]

    # Verify calls to Producer methods.
    actual_kafka_polls = len(producer.poll.call_args_list)
    assert actual_kafka_polls == number_to_process

    actual_produced_records = [(kall.kwargs['key'], kall.kwargs['value']) for kall in producer.produce.call_args_list]
    ts = start_time.timestamp()
    assert actual_produced_records == [
        ("https://localhost/1", worker.Report("https://localhost/1", code=1, timestamp=ts + 1, namelookup=2, connect=3, appconnect=4, pretransfer=5, starttransfer=6, total=7)),
        ("https://localhost/2", worker.Report("https://localhost/2", code=8, timestamp=ts + 2, namelookup=9, connect=10, appconnect=11, pretransfer=12, starttransfer=13, total=14)),
        ("https://localhost/3", worker.Report("https://localhost/3", code=15, timestamp=ts + 3, namelookup=16, connect=17, appconnect=18, pretransfer=19, starttransfer=20, total=21)),
    ]
