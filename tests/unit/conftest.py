# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

# Disable since pytest fixtures require the fixture name as an argument.
# pylint: disable=redefined-outer-name

"""Fixtures for unit tests."""

import os
import typing
from unittest import mock

import pytest
from ops import testing

from src.charm import JenkinsAgentCharm

from . import types


@pytest.fixture
def harness() -> typing.Generator[testing.Harness[JenkinsAgentCharm], None, None]:
    """Create test harness for unit tests."""
    # Create and confifgure harness
    harness = testing.Harness(JenkinsAgentCharm)
    harness.begin()
    harness.disable_hooks()
    harness.update_config(
        {
            "jenkins_url": "",
            "jenkins_agent_name": "",
            "jenkins_agent_token": "",
            "jenkins_agent_labels": "",
        }
    )

    yield harness

    harness.cleanup()


@pytest.fixture(scope="module")
def valid_config():
    """Get valid configuration for the charm."""
    return {
        "jenkins_url": "http://test",
        "jenkins_agent_name": "agent-one",
        "jenkins_agent_token": "token-one",
    }


@pytest.fixture
def harness_pebble_ready(harness: testing.Harness[JenkinsAgentCharm]):
    """Get the charm to the pebble ready state."""
    harness.container_pebble_ready(harness.charm.service_name)

    return harness


@pytest.fixture
def charm_with_jenkins_relation(
    harness_pebble_ready: testing.Harness[JenkinsAgentCharm],
    monkeypatch: pytest.MonkeyPatch,
):
    """Create the jenkins agent charm with an existing relation to jenkins."""
    # Mock uname and CPU count
    mock_os_cpu_count = mock.MagicMock()
    cpu_count = 8
    mock_os_cpu_count.return_value = cpu_count
    monkeypatch.setattr(os, "cpu_count", mock_os_cpu_count)
    mock_os_uname = mock.MagicMock()
    machine_architecture = "x86_64"
    mock_os_uname.return_value.machine = machine_architecture
    monkeypatch.setattr(os, "uname", mock_os_uname)
    # Setup relation
    harness_pebble_ready.enable_hooks()
    remote_app = "jenkins"
    remote_unit_name = f"{remote_app}/0"
    relation_id = harness_pebble_ready.add_relation(relation_name="slave", remote_app=remote_app)
    harness_pebble_ready.add_relation_unit(
        relation_id=relation_id, remote_unit_name=remote_unit_name
    )

    return types.CharmWithJenkinsRelation(
        cpu_count=cpu_count,
        machine_architecture=machine_architecture,
        remote_app=remote_app,
        remote_unit_name=remote_unit_name,
        relation_id=relation_id,
    )
