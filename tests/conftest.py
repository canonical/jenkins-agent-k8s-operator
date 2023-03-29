# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for all tests."""

from pytest import Parser


def pytest_addoption(parser: Parser):
    """Store command line options.

    Args:
        parser: Argument parser.
    """
    parser.addoption("--jenkins-agent-image", action="store")
    parser.addoption("--jenkins-controller-name", action="store")
    parser.addoption("--jenkins-model-name", action="store")
    parser.addoption("--jenkins-unit-number", action="store")
