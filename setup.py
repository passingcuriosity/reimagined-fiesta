"""Setup script for py-latency-logger."""

import os.path
from setuptools import setup


DIR = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(DIR, "README.md")) as f:
    long_description = f.read()

setup(
    name="py-latency-logger",
    version="0.0.1",
    description="Monitor and log request latency of configured URLs.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/thsutton/py-latency-logger",
    license="GPL",
    packages=["latency_logger"],
    package_dir={'': 'src'},
    entry_points={
        "console_scripts": [
            "latency-logger=latency_logger:main",
        ],
    },
    install_requires=[
        "confluent-kafka",
        "pycurl",
        "requests",
        "fastavro",
    ],
    extras_require={
        "dev": [
            "hypothesis",
            "pytest",
            "pytest-mock",
        ],
    },
)
