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

from .constants import ACTIVE_STATUS_NAME, BLOCKED_STATUS_NAME, WAITING_STATUS_NAME


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
    mock_relation_data_content = unittest.mock.MagicMock(spec=ops.RelationDataContent)
    mock_relation_data = unittest.mock.MagicMock(spec=ops.RelationData)
    mock_relation = unittest.mock.MagicMock(spec=ops.Relation)
    mock_relation.name = state.AGENT_RELATION
    mock_relation.data = mock_relation_data
    mock_relation_joined_event = unittest.mock.MagicMock(sepc=ops.RelationJoinedEvent)
    mock_relation_joined_event.relation = mock_relation

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_relation_joined_event)

    mock_relation_data_content.assert_not_called()


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
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given an agent with an monkeypatched workload service that is already registered.
    act: when relation changed event is triggered.
    assert: nothing happens since the agent is already registered.
    """
    monkeypatch.setattr(server, "is_registered", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-k8s-agent", True)
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
    assert: the unit falls into BlockedStatus.
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

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME


def test_agent_relation_changed_validate_credentials_fail(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    agent_credentials: server.Credentials,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given a monkeypatched download_jenkins_agent that raises AgentJarDownloadError.
    act: when _on_agent_relation_changed is called.
    assert: the unit falls into BlockedStatus.
    """
    monkeypatch.setattr(server, "get_credentials", lambda *_args, **_kwargs: agent_credentials)
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: False)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_agent_relation_changed_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME


def test_agent_relation_changed(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    agent_credentials: server.Credentials,
    mock_agent_relation_changed_event: unittest.mock.MagicMock,
):
    """
    arrange: given a monkeypatched download_jenkins_agent that raises AgentJarDownloadError.
    act: when _on_agent_relation_changed is called.
    assert: the unit falls into BlockedStatus.
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
