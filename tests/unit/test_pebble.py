# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s pebble module tests."""

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
import state

_TEST_TOKEN = secrets.token_hex(16)


def test__get_pebble_layer():
    """
    arrange: given a server url, and an agent_token pair.
    act: when _get_pebble_layer is called.
    assert: a pebble layer with jenkins agent service is returned.
    """
    test_url = "http://test-url"
    test_agent_token_pair = ("agent-1", secrets.token_hex(16))
    mock_state = unittest.mock.MagicMock(spec=state.State)
    mock_state.jenkins_agent_service_name = state.State.jenkins_agent_service_name
    pebble_service = pebble.PebbleService(state=mock_state)

    layer = pebble_service._get_pebble_layer(
        server_url=test_url, agent_token_pair=test_agent_token_pair
    )

    assert layer.services["jenkins-agent-k8s"] == {
        "override": "replace",
        "summary": "Jenkins agent k8s",
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


def test_stop_agent_service_not_exists():
    """
    arrange: given a monkeypatched container that raises pebble API service not exists error.
    act: when stop_agent is called.
    assert: nothing happens since the service was not started.
    """
    mock_state = unittest.mock.MagicMock(spec=state.State)
    mock_state.jenkins_agent_service_name = state.State.jenkins_agent_service_name
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.get_service.side_effect = [ops.ModelError()]
    pebble_service = pebble.PebbleService(state=mock_state)

    pebble_service.stop_agent(container=mock_container)

    mock_container.stop.assert_not_called()
    mock_container.remove_path.assert_not_called()


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


@pytest.mark.parametrize(
    "plan_env,expected",
    [
        pytest.param(None, True, id="no_plan"),
        pytest.param({}, True, id="no_service"),
        pytest.param(
            {"JENKINS_URL": "http://old:8080", "JENKINS_TOKEN": _TEST_TOKEN},
            False,
            id="same_credentials",
        ),
        pytest.param(
            {"JENKINS_URL": "http://different:8080", "JENKINS_TOKEN": _TEST_TOKEN},
            True,
            id="url_differs",
        ),
    ],
)
def test_credentials_changed(plan_env: typing.Optional[typing.Dict[str, str]], expected: bool):
    """
    arrange: given various pebble plan states.
    act: when credentials_changed is called.
    assert: returns True when credentials differ from desired.
    """
    mock_state = unittest.mock.MagicMock(spec=state.State)
    mock_state.jenkins_agent_service_name = "jenkins-agent-k8s"
    mock_container = unittest.mock.MagicMock(spec=ops.Container)

    if plan_env is None:
        # Simulate ConnectionError when reading plan
        mock_container.get_plan.side_effect = ops.pebble.ConnectionError("not ready")
    elif not plan_env:
        # Empty plan with no services
        mock_plan = unittest.mock.MagicMock()
        mock_plan.services = {}
        mock_container.get_plan.return_value = mock_plan
    else:
        # Plan with service and environment
        mock_service = unittest.mock.MagicMock()
        mock_service.environment = plan_env
        mock_plan = unittest.mock.MagicMock()
        mock_plan.services = {"jenkins-agent-k8s": mock_service}
        mock_container.get_plan.return_value = mock_plan

    pebble_service = pebble.PebbleService(state=mock_state)

    result = pebble_service.credentials_changed(
        container=mock_container,
        server_url="http://old:8080",
        agent_token=_TEST_TOKEN,
    )
    assert result == expected
