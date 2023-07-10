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

import pebble
import server
import state
from charm import JenkinsAgentCharm


def test__get_pebble_layer(harness: ops.testing.Harness):
    """
    arrange: given a server url, and an agent_token pair.
    act: when _get_pebble_layer is called.
    assert: a pebble layer with jenkins agent service is returned.
    """
    test_url = "http://test-url"
    test_agent_token_pair = ("agent-1", secrets.token_hex(16))
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    layer = jenkins_charm.pebble_service._get_pebble_layer(
        server_url=test_url, agent_token_pair=test_agent_token_pair
    )

    assert layer.services["jenkins-k8s-agent"] == {
        "override": "replace",
        "summary": "Jenkins k8s agent",
        "command": str(server.ENTRYSCRIPT_PATH),
        "environment": {
            "JENKINS_URL": test_url,
            "JENKINS_AGENT": test_agent_token_pair[0],
            "JENKINS_TOKEN": test_agent_token_pair[1],
        },
        "startup": "enabled",
        "user": server.USER,
    }


def test_reconcile():
    """
    arrange: given a server url, and an agent_token pair.
    act: when reconcile is called.
    assert: pebble service is initialized and the unit status becomes Active.
    """
    mock_state = unittest.mock.MagicMock(spec=state.State)
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    pebble_service = pebble.PebbleService(state=mock_state)

    pebble_service.reconcile(
        server_url="test_url",
        agent_token_pair=("test_agent", secrets.token_hex(16)),
        container=mock_container,
    )

    mock_container.add_layer.assert_called_once()
    mock_container.replan.assert_called_once()


def test_stop_agent():
    """
    arrange: given a monkeypatched _jenkins_agent_container representing non connectable container.
    act: when stop_agent is called.
    assert: nothing happens since the workload should not be ready yet.
    """
    mock_state = unittest.mock.MagicMock(spec=state.State)
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    pebble_service = pebble.PebbleService(state=mock_state)

    pebble_service.stop_agent(container=mock_container)

    mock_container.stop.assert_called_once()
    mock_container.remove_path.assert_called_once()
