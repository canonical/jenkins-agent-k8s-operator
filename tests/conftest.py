# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for jenkins-agent-k8s charm tests."""

import pytest


def pytest_addoption(parser: pytest.Parser):
    """Parse additional pytest options.

    Args:
        parser: pytest command line parser.
    """
    # The Jenkins agent k8s image name:tag.
    parser.addoption("--jenkins-agent-k8s-image", action="store", default="")
    # The prebuilt charm file.
    parser.addoption("--charm-file", action="store", default="")
    # The path to kubernetes config.
    parser.addoption("--kube-config", action="store", default="~/.kube/config")
