# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s agent module tests."""

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
    arrange: given an agent.
    act: when a agent relation joined event is triggered.
    assert: the unit updates databag adhering to jenkins_agent_v0 interface.
    """
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_config(config)
    harness.begin_with_initial_hooks()
    model_relation = harness.model.get_relation(state.AGENT_RELATION, relation_id)
    assert model_relation, "Relation cannot be None"
    jenkins_unit = next(iter(model_relation.units))
    mock_relation_data_content = unittest.mock.MagicMock(spec=ops.RelationDataContent)
    mock_relation_data = {jenkins_unit: mock_relation_data_content}
    mock_relation = unittest.mock.MagicMock(spec=ops.Relation)
    mock_relation.name = state.AGENT_RELATION
    mock_relation.data = mock_relation_data
    mock_relation_joined_event = unittest.mock.MagicMock(sepc=ops.RelationJoinedEvent)
    mock_relation_joined_event.relation = mock_relation

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_joined(mock_relation_joined_event)

    mock_relation_data_content.update.assert_not_called()


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
    assert relation_data.get("executors")
    assert relation_data.get("labels")
    assert relation_data.get("name")


def test_agent_relation_changed_relation_config_priority(
    harness: ops.testing.Harness,
    config: typing.Dict[str, str],
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
):
    """
    arrange: given an agent with juju configuration values.
    act: when relation changed event is triggered.
    assert: nothing happens since configuration values take priority.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.update_config(config)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_event)

    mock_event.defer.assert_not_called()


def test_agent_relation_changed_container_not_ready(
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
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_event)

    mock_event.defer.assert_called_once()


def test_agent_relation_changed_service_running(
    harness: ops.testing.Harness,
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
):
    """
    arrange: given a workload container with existing $JENKINS_HOME/agents/.ready file.
    act: when relation changed event is triggered.
    assert: nothing happens since the agent is already registered.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.set_can_connect("jenkins-agent-k8s", True)
    container = harness.model.unit.get_container("jenkins-agent-k8s")
    container.push(server.AGENT_READY_PATH, "test", encoding="utf-8", make_dirs=True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_event)

    mock_event.defer.assert_not_called()


def test_agent_relation_changed_incomplete_relation_data(
    harness: ops.testing.Harness,
    get_mock_relation_changed_event: typing.Callable[[str], ops.RelationChangedEvent],
):
    """
    arrange: given an agent with incomplete relation data.
    act: when relation changed event is triggered.
    assert: charm falls into waiting status.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.set_can_connect("jenkins-agent-k8s", True)
    relation_id = harness.add_relation(state.AGENT_RELATION, remote_app="jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(relation_id, "jenkins/0", {"url": "test"})
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME


def test_agent_relation_changed_download_jenkins_agent_fail(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    raise_exception: typing.Callable,
    get_event_relation_data: typing.Callable[
        [str], typing.Tuple[unittest.mock.MagicMock, typing.Dict[str, str]]
    ],
):
    """
    arrange: given a monkeypatched download_jenkins_agent that raises AgentJarDownloadError.
    act: when _on_agent_relation_changed is called.
    assert: the unit falls into ErroredStatus.
    """
    (mock_event, relation_data) = get_event_relation_data(state.AGENT_RELATION)
    # The monkeypatched attribute download_jenkins_agent is used across unit tests.
    monkeypatch.setattr(
        server,  # pylint: disable=duplicate-code
        "download_jenkins_agent",
        lambda *_args, **_kwargs: raise_exception(server.AgentJarDownloadError),
    )
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
    with pytest.raises(server.AgentJarDownloadError) as exc:
        jenkins_charm.agent_observer._on_agent_relation_changed(mock_event)

        assert exc.value == "Failed to download Jenkins agent executable."


def test_agent_relation_changed(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    get_event_relation_data: typing.Callable[
        [str], typing.Tuple[unittest.mock.MagicMock, typing.Dict[str, str]]
    ],
):
    """
    arrange: given a monkeypatched server actions that pass.
    act: when _on_agent_relation_changed is called.
    assert: the unit falls into ActiveStatus.
    """
    (mock_event, relation_data) = get_event_relation_data(state.AGENT_RELATION)
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
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
    jenkins_charm.agent_observer._on_agent_relation_changed(mock_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test_agent_relation_departed_container_not_ready(
    monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness
):
    """
    arrange: given a container that is not ready and a monkeypatched pebble stop_agent.
    act: when _on_agent_relation_departed is called.
    assert: the unit falls into BlockedStatus.
    """
    mock_stop_agent = unittest.mock.MagicMock(spec=pebble.PebbleService.stop_agent)
    monkeypatch.setattr(pebble.PebbleService, "stop_agent", mock_stop_agent)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationDepartedEvent)
    harness.set_can_connect("jenkins-agent-k8s", False)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_departed(mock_event)

    mock_stop_agent.assert_not_called()


def test_agent_relation_departed(monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness):
    """
    arrange: given a monkeypatched pebble service and an agent that is departing the relation.
    act: when _on_agent_relation_departed is called.
    assert: the unit falls into BlockedStatus.
    """
    monkeypatch.setattr(pebble.PebbleService, "stop_agent", lambda *_args, **_kwargs: None)
    mock_event = unittest.mock.MagicMock(spec=ops.RelationDepartedEvent)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm.agent_observer._on_agent_relation_departed(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Waiting for config/relation."
