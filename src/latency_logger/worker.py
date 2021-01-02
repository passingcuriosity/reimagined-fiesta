"""Code to execute tasks."""

import dataclasses
import logging
import multiprocessing
import queue
import signal
from dataclasses import dataclass
from datetime import datetime

import pycurl
from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer


@dataclass(frozen=True)
class Report:
    """Report for a request."""

    url: str
    code: int
    timestamp: float
    namelookup: float
    connect: float
    appconnect: float
    pretransfer: float
    starttransfer: float
    total: float

    SCHEMA = """
    {
        "namespace": "com.passingcuriosity.latency_logger",
        "name": "Report",
        "type": "record",
        "fields": [
            {"name": "url", "type": "string", "comment": "URL requested."},
            {"name": "code", "type": "int", "comment": "HTTP response code."},
            {"name": "timestamp", "type": "double", "comment": "POSIX timestamp of request.", "default": 0.0},
            {"name": "namelookup", "type": "double", "comment": "Time to resolve name."},
            {"name": "connect", "type": "double", "comment": "Time to connect."},
            {"name": "appconnect", "type": "double", "comment": "Time to initialise TLS."},
            {"name": "pretransfer", "type": "double", "comment": "Time to negotiate, setup, etc."},
            {"name": "starttransfer", "type": "double", "comment": "Time to first byte."},
            {"name": "total", "type": "double", "comment": "Time to complete request."}
        ]
    }
    """

    @staticmethod
    def asdict(self, ctx):
        """Convert to a dictionary for Avro serialisation."""
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class Config:
    """Configuration for worker processes."""

    topic: str
    schema_registry: str
    bootstrap_servers: str
    ca_cert: str
    auth_key: str
    auth_cert: str
    verbose: bool = False


def main(
    name: str,
    shutdown: multiprocessing.Value,
    request_queue: multiprocessing.Queue,
    config: Config
) -> None:
    """Execute tasks forever.

    This method is the entrypoint for the worker which executes the monitoring
    tasks. It is executed in a dedicate child process.
    """
    if config.verbose:
        logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(name)
    log.info(f"Starting process {name}.")

    # SIGINT will be delivered to the whole process group. We'll need to ignore
    # it in the worker processes to give them the opportunity to finish any
    # pending work.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    schema_registry_client = SchemaRegistryClient({
        'url': config.schema_registry
    })
    avro_serializer = AvroSerializer(
        Report.SCHEMA,
        schema_registry_client,
        Report.asdict
    )

    producer = SerializingProducer({
        'client.id': name,
        'bootstrap.servers': config.bootstrap_servers,
        'key.serializer': StringSerializer('utf_8'),
        'security.protocol': 'SSL',
        'ssl.key.location': config.auth_key,
        'ssl.certificate.location': config.auth_cert,
        'ssl.ca.location': config.ca_cert,
        'value.serializer': avro_serializer,
    })
    err = _report_error(log)

    while not shutdown.value:
        producer.poll(0.0)
        try:
            now = datetime.now()
            req = request_queue.get(timeout=1)
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, req)
            curl.setopt(pycurl.CONNECTTIMEOUT, 30)
            curl.setopt(pycurl.TIMEOUT, 300)
            curl.setopt(pycurl.NOSIGNAL, 1)
            curl.setopt(pycurl.WRITEFUNCTION, len)
            try:
                curl.perform()
                report = Report(
                    timestamp=now.timestamp(),
                    url=req,
                    code=int(curl.getinfo(pycurl.RESPONSE_CODE)),
                    namelookup=curl.getinfo(pycurl.NAMELOOKUP_TIME),
                    connect=curl.getinfo(pycurl.CONNECT_TIME),
                    appconnect=curl.getinfo(pycurl.APPCONNECT_TIME),
                    pretransfer=curl.getinfo(pycurl.PRETRANSFER_TIME),
                    starttransfer=curl.getinfo(pycurl.STARTTRANSFER_TIME),
                    total=curl.getinfo(pycurl.TOTAL_TIME),
                )
                log.info(str(report))
                producer.produce(
                    topic=config.topic,
                    key=req,
                    value=report,
                    on_delivery=err
                )
            except TypeError:
                # It'll never work if we misconfigure PycURL.
                raise
            except pycurl.error as exc:
                # TODO: Record the failure in Kafka.
                log.warning(f"Failed to retrieve {req}", exc)
            # TODO: Handle exceptions from the Kafka Producer.
            finally:
                curl.close()
        except queue.Empty:
            log.debug("No request to process.")
    # Flush any results that haven't been committed yet.
    log.warning(f"Process {name} shutting down.")
    producer.flush()


def _report_error(log):
    """Return a callback to report errors in writing to Kafka."""
    def error_reporter(err, msg):
        if err is not None:
            log.error(f"Couldn't publish message about {msg.key()}: {err}")

    return error_reporter
