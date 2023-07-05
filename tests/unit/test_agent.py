# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-k8s-agent agent module tests."""

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

from .constants import (
    ACTIVE_STATUS_NAME,
    BLOCKED_STATUS_NAME,
    ERRORED_STATUS_NAME,
    WAITING_STATUS_NAME,
)


def test_agent_relation_joined_config_priority(
    harness: ops.testing.Harness, config: typing.Dict[str, str]
):
    """
    arrange: given an agent.
    act: when a slave relation joined event is triggered.
    assert: the unit updates databag adhering to jenkins-slave interface.
    """
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_config(config)
    harness.begin_with_initial_hooks()
    relation = harness.model.get_relation(state.AGENT_RELATION, relation_id)
    assert relation, "Relation cannot be None"
    jenkins_unit = next(iter(relation.units))
    mock_relation_data_content = unittest.mock.MagicMock(spec=ops.RelationDataContent)
    mock_relation_data = {jenkins_unit: mock_relation_data_content}
    mock_relation = unittest.mock.MagicMock(spec=ops.Relation)
    mock_relation.name = state.AGENT_RELATION
    mock_relation.data = mock_relation_data
    mock_relation_joined_event = unittest.mock.MagicMock(sepc=ops.RelationJoinedEvent)
    mock_relation_joined_event.relation = mock_relation

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_relation_joined_event)

    mock_relation_data_content.update.assert_not_called()


def test_agent_relation_joined_slave_relation(harness: ops.testing.Harness):
    """
    arrange: given an agent.
    act: when a slave relation joined event is triggered.
    assert: the unit updates databag adhering to jenkins-slave interface.
    """
    relation_id = harness.add_relation(state.SLAVE_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")

    harness.begin_with_initial_hooks()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    relation_data = harness.get_relation_data(relation_id, jenkins_charm.unit.name)
    assert "executors" in relation_data and relation_data["executors"]
    assert "labels" in relation_data and relation_data["labels"]
    assert "slavehost" in relation_data and relation_data["slavehost"]


def test_agent_relation_joined_agent_relation(harness: ops.testing.Harness):
    """
    arrange: given an agent.
    act: when an agent relation joined event is triggered.
    assert: the unit updates databag adhering to jenkins_agent_v0 interface.
    """
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")

    harness.begin_with_initial_hooks()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    relation_data = harness.get_relation_data(relation_id, jenkins_charm.unit.name)
    assert "executors" in relation_data and relation_data["executors"]
    assert "labels" in relation_data and relation_data["labels"]
    assert "name" in relation_data and relation_data["name"]


def test_agent_relation_changed_relation_config_priority(
    harness: ops.testing.Harness,
    config: typing.Dict[str, str],
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given an agent with juju configuration values.
    act: when relation changed event is triggered.
    assert: nothing happens since configuration values take priority.
    """
    harness.update_config(config)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    mock_agent_relation_changed_event.defer.assert_not_called()


def test_agent_relation_changed_container_not_ready(
    harness: ops.testing.Harness, mock_agent_relation_changed_event: unittest.mock.MagicMock
):
    """
    arrange: given an agent with the workload container not yet ready.
    act: when relation changed event is triggered.
    assert: the relation changed event is deferred.
    """
    harness.set_can_connect("jenkins-k8s-agent", False)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    mock_agent_relation_changed_event.defer.assert_called_once()


def test_agent_relation_changed_service_running(
    harness: ops.testing.Harness,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given a workload container with existing $JENKINS_HOME/agents/.ready file.
    act: when relation changed event is triggered.
    assert: nothing happens since the agent is already registered.
    """
    harness.set_can_connect("jenkins-k8s-agent", True)
    container = harness.model.unit.get_container("jenkins-k8s-agent")
    container.push(server.AGENT_READY_PATH, "test", encoding="utf-8", make_dirs=True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    mock_agent_relation_changed_event.defer.assert_not_called()


def test_agent_relation_changed_incomplete_relation_data(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given an agent with monkeypatched get_credentials which returns None.
    act: when relation changed event is triggered.
    assert: charm falls into waiting status.
    """
    monkeypatch.setattr(server, "get_credentials", lambda *_args, **_kwargs: None)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME


def test_agent_relation_changed_download_jenkins_agent_fail(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    raise_exception: typing.Callable,
    agent_credentials: server.Credentials,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given a monkeypatched download_jenkins_agent that raises AgentJarDownloadError.
    act: when _on_agent_relation_changed is called.
    assert: the unit falls into ErroredStatus.
    """
    monkeypatch.setattr(server, "get_credentials", lambda *_args, **_kwargs: agent_credentials)
    # The monkeypatched attribute download_jenkins_agent is used across unit tests.
    monkeypatch.setattr(
        server,  # pylint: disable=duplicate-code
        "download_jenkins_agent",
        lambda *_args, **_kwargs: raise_exception(server.AgentJarDownloadError),
    )
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    assert jenkins_charm.unit.status.name == ERRORED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Failed to download Jenkins agent executable."


def test_agent_relation_changed_validate_credentials_fail(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    agent_credentials: server.Credentials,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given a monkeypatched validate_credentials that fails.
    act: when _on_agent_relation_changed is called.
    assert: the unit falls into WaitingStatus.
    """
    monkeypatch.setattr(server, "get_credentials", lambda *_args, **_kwargs: agent_credentials)
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: False)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Waiting for credentials."


def test_agent_relation_changed(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    agent_credentials: server.Credentials,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given a monkeypatched server actions that pass.
    act: when _on_agent_relation_changed is called.
    assert: the unit falls into ActiveStatus.
    """
    monkeypatch.setattr(server, "get_credentials", lambda *_args, **_kwargs: agent_credentials)
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test_agent_relation_departed(monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness):
    """
    arrange: given a monkeypatched pebble service and an agent that is departing the relation.
    act: when _on_agent_relation_departed is called.
    assert: the unit falls into BlockedStatus.
    """
    monkeypatch.setattr(pebble.PebbleService, "stop_agent", lambda *_args, **_kwargs: None)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationDepartedEvent)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_departed(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Waiting for config/relation."


def test_slave_relation_departed(monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness):
    """
    arrange: given a monkeypatched pebble service and an agent that is departing the relation.
    act: when _on_slave_relation_departed is called.
    assert: the unit falls into BlockedStatus.
    """
    monkeypatch.setattr(pebble.PebbleService, "stop_agent", lambda *_args, **_kwargs: None)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationDepartedEvent)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_slave_relation_departed(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Waiting for config/relation."
