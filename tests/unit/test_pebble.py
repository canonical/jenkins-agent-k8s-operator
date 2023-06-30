# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-k8s-agent pebble module tests."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import secrets
import typing
import unittest.mock

import ops
import ops.testing
import pytest

import pebble
import server
from charm import JenkinsAgentCharm

from .constants import ACTIVE_STATUS_NAME


def test__get_pebble_layer(harness: ops.testing.Harness):
    """
    arrange: given a server url, and an agent_token pair.
    act: when _get_pebble_layer is called.
    assert: a pebble layer with jenkins agent service is returned.
    """
    test_url = "http://test-url"
    test_agent_token_pairs = (("agent-1", secrets.token_hex(16)),)
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    layer = jenkins_charm.pebble_service._get_pebble_layer(
        server_url=test_url, agent_token_pairs=test_agent_token_pairs
    )

    assert layer.services["jenkins-k8s-agent"] == {
        "override": "replace",
        "summary": "Jenkins k8s agent",
        "command": str(server.ENTRYSCRIPT_PATH),
        "environment": {
            "JENKINS_URL": test_url,
            "JENKINS_AGENTS": test_agent_token_pairs[0][0],
            "JENKINS_TOKENS": test_agent_token_pairs[0][1],
        },
        "startup": "enabled",
        "user": server.USER,
        "group": server.GROUP,
    }


def test_reconcile(harness: ops.testing.Harness):
    """
    arrange: given a server url, and an agent_token pair.
    act: when reconcile is called.
    assert: pebble service is initialized and the unit status becomes Active.
    """
    test_url = "http://test-url"
    test_agent_token_pairs = (("agent-1", secrets.token_hex(16)),)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.pebble_service.reconcile(
        server_url=test_url, agent_token_pairs=test_agent_token_pairs
    )

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test_stop_agent_no_container(monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness):
    """
    arrange: given a monkeypatched _jenkins_agent_container representing non connectable container.
    act: when stop_agent is called.
    assert: nothing happens since the workload should not be ready yet.
    """
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.can_connect.return_value = False
    monkeypatch.setattr(pebble.PebbleService, "_jenkins_agent_container", mock_container)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.pebble_service.stop_agent()

    mock_container.stop.assert_not_called()


def test_stop_agent(monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness):
    """
    arrange: given a monkeypatched _jenkins_agent_container representing non connectable container.
    act: when stop_agent is called.
    assert: nothing happens since the workload should not be ready yet.
    """
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.can_connect.return_value = True
    monkeypatch.setattr(pebble.PebbleService, "_jenkins_agent_container", mock_container)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.pebble_service.stop_agent()

    mock_container.stop.assert_called_once()
    mock_container.remove_path.assert_called_once()
