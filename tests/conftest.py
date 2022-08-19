# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for all tests."""


def pytest_addoption(parser):
    """Store command line options."""
    parser.addoption("--jenkins-agent-image", action="store")
