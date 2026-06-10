# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s agent relation handling tests."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import typing
import unittest.mock

import ops.testing
import pytest

import pebble
import server
import state
from charm import JenkinsAgentCharm

from .constants import ACTIVE_STATUS_NAME, BLOCKED_STATUS_NAME, WAITING_STATUS_NAME


def test_agent_relation_joined_config_priority(
    harness: ops.testing.Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given an agent with config set.
    act: when a agent relation joined event is triggered (reconcile fires).
    assert: config mode blocks; databag is not populated with agent metadata.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_config(config)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationJoinedEvent)
    jenkins_charm._on_reconcile(mock_event)

    # Config takes priority — relation databag should not have agent metadata.
    relation_data = harness.get_relation_data(relation_id, jenkins_charm.unit.name)
    assert "executors" not in relation_data


def test_agent_relation_joined_agent_relation(
    harness: ops.testing.Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given an agent.
    act: when an agent relation joined event is triggered (reconcile fires).
    assert: the unit updates databag adhering to jenkins_agent_v0 interface.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(
        relation_id,
        "jenkins/0",
        {"url": "http://10.1.69.130:8080", "jenkins-agent-k8s-0_secret": "token123"},
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationJoinedEvent)
    jenkins_charm._on_reconcile(mock_event)

    relation_data = harness.get_relation_data(relation_id, jenkins_charm.unit.name)
    assert relation_data.get("executors")
    assert relation_data.get("labels")
    assert relation_data.get("name")


def test_reconcile_relation_config_priority(
    harness: ops.testing.Harness,
    config: typing.Dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
):
    """
    arrange: given an agent with juju configuration values.
    act: when relation changed event is triggered.
    assert: nothing happens since configuration values take priority.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    # Config mode succeeds without deferring
    mock_event.defer.assert_not_called()


def test_reconcile_container_not_ready(
    harness: ops.testing.Harness,
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
):
    """
    arrange: given an agent with the workload container not yet ready.
    act: when relation changed event is triggered.
    assert: the relation changed event is deferred.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.set_can_connect("jenkins-agent-k8s", False)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    mock_event.defer.assert_called_once()


@pytest.mark.parametrize(
    "creds_changed,expect_active",
    [
        pytest.param(False, True, id="no_change"),
        pytest.param(True, True, id="credentials_changed"),
    ],
)
def test_reconcile_service_running(
    harness: ops.testing.Harness,
    monkeypatch: pytest.MonkeyPatch,
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
    creds_changed: bool,
    expect_active: bool,
):
    """
    arrange: given a workload container with existing $JENKINS_HOME/agents/.ready file.
    act: when reconcile is triggered.
    assert: agent restarts only when credentials have changed.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.set_can_connect("jenkins-agent-k8s", True)
    container = harness.model.unit.get_container("jenkins-agent-k8s")
    container.push(server.AGENT_READY_PATH, "test", encoding="utf-8", make_dirs=True)
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(
        relation_id,
        "jenkins/0",
        {"url": "http://10.1.69.130:8080", "jenkins-agent-k8s-0_secret": "token123"},
    )
    monkeypatch.setattr(
        pebble.PebbleService, "credentials_changed", lambda *_args, **_kwargs: creds_changed
    )
    monkeypatch.setattr(pebble.PebbleService, "stop_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test_reconcile_server_not_ready(
    harness: ops.testing.Harness,
    monkeypatch: pytest.MonkeyPatch,
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
):
    """
    arrange: given an agent running with old credentials and server not reachable at new URL.
    act: when reconcile is triggered with new server URL.
    assert: event is deferred and agent continues running on old credentials.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.set_can_connect("jenkins-agent-k8s", True)
    container = harness.model.unit.get_container("jenkins-agent-k8s")
    container.push(server.AGENT_READY_PATH, "test", encoding="utf-8", make_dirs=True)
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(
        relation_id,
        "jenkins/0",
        {"url": "http://10.1.69.130:8080", "jenkins-agent-k8s-0_secret": "token123"},
    )
    monkeypatch.setattr(
        pebble.PebbleService, "credentials_changed", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: False)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME
    mock_event.defer.assert_called_once()


def test_reconcile_incomplete_relation_data(
    harness: ops.testing.Harness,
    get_mock_relation_changed_event: typing.Callable[[str], ops.RelationChangedEvent],
):
    """
    arrange: given an agent with incomplete relation data.
    act: when reconcile is triggered.
    assert: charm falls into waiting status.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.set_can_connect("jenkins-agent-k8s", True)
    relation_id = harness.add_relation(state.AGENT_RELATION, remote_app="jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(relation_id, "jenkins/0", {"url": "test"})
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME


def test_reconcile_download_jenkins_agent_fail(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    raise_exception: typing.Callable,
    get_event_relation_data: typing.Callable[
        [str], typing.Tuple[unittest.mock.MagicMock, typing.Dict[str, str]]
    ],
):
    """
    arrange: given a monkeypatched download_jenkins_agent that raises AgentJarDownloadError.
    act: when reconcile is called.
    assert: the event is deferred and unit enters WaitingStatus.
    """
    (mock_event, relation_data) = get_event_relation_data(state.AGENT_RELATION)
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        lambda *_args, **_kwargs: raise_exception(server.AgentJarDownloadError),
    )
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(
        relation_id=relation_id,
        app_or_unit="jenkins/0",
        key_values=relation_data,
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME
    mock_event.defer.assert_called_once()


def test_reconcile_success(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    get_event_relation_data: typing.Callable[
        [str], typing.Tuple[unittest.mock.MagicMock, typing.Dict[str, str]]
    ],
):
    """
    arrange: given a monkeypatched server actions that pass.
    act: when reconcile is called.
    assert: the unit falls into ActiveStatus.
    """
    (mock_event, relation_data) = get_event_relation_data(state.AGENT_RELATION)
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(
        relation_id=relation_id,
        app_or_unit="jenkins/0",
        key_values=relation_data,
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test_agent_relation_departed_container_not_ready(
    monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness
):
    """
    arrange: given a container that is not ready and a monkeypatched pebble stop_agent.
    act: when reconcile fires after relation departed.
    assert: the event is deferred (container not ready), stop_agent not called.
    """
    mock_stop_agent = unittest.mock.MagicMock(spec=pebble.PebbleService.stop_agent)
    monkeypatch.setattr(pebble.PebbleService, "stop_agent", mock_stop_agent)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationDepartedEvent)
    harness.set_can_connect("jenkins-agent-k8s", False)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    mock_stop_agent.assert_not_called()
    mock_event.defer.assert_called_once()


def test_agent_relation_departed(monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness):
    """
    arrange: given a monkeypatched pebble service and an agent that is departing the relation.
    act: when reconcile fires after relation departed (no relation present).
    assert: the unit falls into BlockedStatus.
    """
    monkeypatch.setattr(pebble.PebbleService, "stop_agent", lambda *_args, **_kwargs: None)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationDepartedEvent)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Waiting for config/relation."
