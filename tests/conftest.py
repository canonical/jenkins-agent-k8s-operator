# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.


def pytest_addoption(parser):
    parser.addoption("--jenkins-agent-image", action="store")
