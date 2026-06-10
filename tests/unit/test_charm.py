# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s charm module tests."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import typing
from unittest.mock import MagicMock

import ops
import pytest
from ops.testing import Harness

import server
import state
from charm import JenkinsAgentCharm

from .constants import ACTIVE_STATUS_NAME, BLOCKED_STATUS_NAME, WAITING_STATUS_NAME


def test___init___invalid_state(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, raise_exception: typing.Callable
):
    """
    arrange: given a monkeypatched State.from_charm that raises an InvalidState Error.
    act: when the JenkinsAgentCharm is initialized.
    assert: The agent falls into BlockedStatus.
    """
    invalid_state_message = "Invalid executor message"
    monkeypatch.setattr(
        state.State,
        "from_charm",
        lambda *_args, **_kwargs: raise_exception(state.InvalidStateError(invalid_state_message)),
    )
    harness.begin_with_initial_hooks()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == invalid_state_message


def test_agent_relation_joined_invalid_state(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, raise_exception: typing.Callable
):
    """
    arrange: given a charm where State.from_charm raises InvalidStateError.
    act: when the agent relation joined event fires.
    assert: The unit falls into BlockedStatus.
    """
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    invalid_state_message = "Invalid state on join"
    monkeypatch.setattr(
        state.State,
        "from_charm",
        lambda *_args, **_kwargs: raise_exception(state.InvalidStateError(invalid_state_message)),
    )
    relation_id = harness.add_relation("agent", "jenkins-k8s")
    harness.add_relation_unit(relation_id, "jenkins-k8s/0")

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == invalid_state_message


def test_agent_relation_departed_invalid_state(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, raise_exception: typing.Callable
):
    """
    arrange: given a charm where State.from_charm raises InvalidStateError.
    act: when the agent relation departed event fires.
    assert: The unit falls into BlockedStatus.
    """
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    relation_id = harness.add_relation("agent", "jenkins-k8s")
    harness.add_relation_unit(relation_id, "jenkins-k8s/0")
    invalid_state_message = "Invalid state on depart"
    monkeypatch.setattr(
        state.State,
        "from_charm",
        lambda *_args, **_kwargs: raise_exception(state.InvalidStateError(invalid_state_message)),
    )
    harness.remove_relation(relation_id)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == invalid_state_message


def test_reconcile_container_not_ready(harness: Harness):
    """
    arrange: given a charm with a workload container that is not ready yet.
    act: when _on_reconcile is called.
    assert: the event is deferred.
    """
    harness.set_can_connect("jenkins-agent-k8s", False)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    mock_event.defer.assert_called_once()


def test_reconcile_no_config_no_relation(harness: Harness):
    """
    arrange: given a charm with no configured state nor relation.
    act: when _on_reconcile is called.
    assert: the unit falls into BlockedStatus.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Waiting for config/relation."


def test_reconcile_config_with_relation_blocks(harness: Harness, config: typing.Dict[str, str]):
    """
    arrange: given a charm with config values AND an agent relation present.
    act: when _on_reconcile is called.
    assert: the unit falls into BlockedStatus asking to remove relation.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Please remove and re-relate agent relation."


def test_reconcile_config_download_agent_error(
    monkeypatch: pytest.MonkeyPatch,
    raise_exception: typing.Callable,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched download_jenkins_agent that raises an exception.
    act: when _on_reconcile is called.
    assert: unit defers and enters WaitingStatus.
    """
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        lambda *_args, **_kwargs: raise_exception(server.AgentJarDownloadError),
    )
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME
    mock_event.defer.assert_called_once()


def test_reconcile_config_no_valid_credentials(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched validate_credentials that returns false.
    act: when _on_reconcile is called.
    assert: unit falls into BlockedStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Additional valid agent-token pairs required."


def test_reconcile_config_success(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched server functions that returns passing values.
    act: when _on_reconcile is called.
    assert: unit falls into ActiveStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.ConfigChangedEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test_reconcile_upgrade_charm(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, config: typing.Dict[str, str]
):
    """
    arrange: given a charm with monkeypatched server functions that returns passing values.
    act: when _on_reconcile is called via upgrade_charm event.
    assert: unit falls into ActiveStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.UpgradeCharmEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test_reconcile_pebble_ready_container_not_ready(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given a charm container that is not yet connectable.
    act: when _on_reconcile is called via pebble_ready event.
    assert: the event is deferred.
    """
    harness.begin()
    charm = typing.cast(JenkinsAgentCharm, harness.charm)
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        (mock_download_func := MagicMock(spec=server.download_jenkins_agent)),
    )
    mock_event = MagicMock(spec=ops.PebbleReadyEvent)

    charm._on_reconcile(mock_event)

    mock_download_func.assert_not_called()
    mock_event.defer.assert_called_once()


def test_reconcile_pebble_ready_with_relation(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a connected container and valid relation credentials.
    act: when _on_reconcile is called via pebble_ready event.
    assert: the charm downloads agent and enters ActiveStatus.
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
    mock_event = MagicMock(spec=ops.PebbleReadyEvent)

    charm = typing.cast(JenkinsAgentCharm, harness.charm)
    charm._on_reconcile(mock_event)

    assert charm.unit.status.name == ACTIVE_STATUS_NAME


def test_reconcile_server_not_ready_config(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with config but server not reachable.
    act: when _on_reconcile is called.
    assert: event is deferred with WaitingStatus.
    """
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: False)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == WAITING_STATUS_NAME
    mock_event.defer.assert_called_once()
