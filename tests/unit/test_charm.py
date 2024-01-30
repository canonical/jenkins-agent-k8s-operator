# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s charm module tests."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import secrets
import typing
from unittest.mock import MagicMock

import ops
import pytest
from ops.testing import Harness

import server
import state
from charm import JenkinsAgentCharm

from .constants import ACTIVE_STATUS_NAME, BLOCKED_STATUS_NAME


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


def test__register_agent_from_config_container_not_ready(harness: Harness):
    """
    arrange: given a charm with a workload container that is not ready yet.
    act: when _register_agent_from_config is called.
    assert: the event is deferred.
    """
    harness.set_can_connect("jenkins-agent-k8s", False)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_config_changed(mock_event)

    mock_event.defer.assert_called_once()


def test__register_agent_from_config_no_config_state(harness: Harness):
    """
    arrange: given a charm with no configured state nor relation.
    act: when _register_agent_from_config is called.
    assert: the unit falls into BlockedStatus.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_config_changed(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Waiting for config/relation."


def test__register_agent_from_config_use_relation(harness: Harness):
    """
    arrange: given a charm with an agent relation but no configured state.
    act: when _register_agent_from_config is called.
    assert: the nothing happens since agent observer should be handling the relation.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_config_changed(mock_event)

    mock_event.defer.assert_not_called()


def test__register_agent_from_config_download_agent_error(
    monkeypatch: pytest.MonkeyPatch,
    raise_exception: typing.Callable,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched download_jenkins_agent that raises an exception.
    act: when _register_agent_from_config is called.
    assert: unit falls into BlockedStatus.
    """
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        lambda *_args, **_kwargs: raise_exception(server.AgentJarDownloadError),
    )
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)

    with pytest.raises(server.AgentJarDownloadError) as exc:
        jenkins_charm._on_config_changed(mock_event)
        assert exc.value == "Failed to download Agent JAR executable."


def test__register_agent_from_config_no_valid_credentials(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched validate_credentials that returns false.
    act: when _on_config_changed is called.
    assert: unit falls into BlockedStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: False)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_config_changed(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Additional valid agent-token pairs required."


def test__register_agent_from_config_fallback_relation_agent(
    harness: Harness,
):
    """
    arrange: given a charm with reset config values and a agent relation.
    act: when _on_config_changed is called.
    assert: unit falls into BlockedStatus, this should support fallback relation later.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config({})
    harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.begin()

    mock_event = MagicMock(spec=ops.HookEvent)
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_config_changed(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Please remove and re-relate agent relation."


def test__register_agent_from_config(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched server functions that returns passing values.
    act: when _register_agent_from_config is called.
    assert: unit falls into ActiveStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.ConfigChangedEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_config_changed(mock_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test__on_upgrade_charm(
    monkeypatch: pytest.MonkeyPatch, harness: Harness, config: typing.Dict[str, str]
):
    """
    arrange: given a charm with monkeypatched server functions that returns passing values.
    act: when _on_upgrade_charm is called.
    assert: unit falls into ActiveStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.UpgradeCharmEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_upgrade_charm(mock_event)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


def test__on_jenkins_agent_k8s_pebble_ready_container_not_ready(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given a charm container that is not yet connectable.
    act: when _on_jenkins_agent_k8s_pebble_ready is called.
    assert: the charm is not started.
    """
    harness.begin()
    charm = typing.cast(JenkinsAgentCharm, harness.charm)
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        (mock_download_func := MagicMock(spec=server.download_jenkins_agent)),
    )

    charm._on_jenkins_agent_k8s_pebble_ready(MagicMock(spec=ops.PebbleReadyEvent))

    mock_download_func.assert_not_called()


def test__on_jenkins_agent_k8s_pebble_ready_agent_download_error(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given a mocked server download that raises an error.
    act: when _on_jenkins_agent_k8s_pebble_ready is called.
    assert: RuntimeError is raised.
    """
    harness.set_can_connect(state.State.jenkins_agent_service_name, True)
    harness.begin()
    charm = typing.cast(JenkinsAgentCharm, harness.charm)
    charm.state.agent_relation_credentials = server.Credentials(
        address="test", secret=secrets.token_hex(16)
    )
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        MagicMock(spec=server.download_jenkins_agent, side_effect=[server.AgentJarDownloadError]),
    )

    with pytest.raises(server.AgentJarDownloadError):
        charm._on_jenkins_agent_k8s_pebble_ready(MagicMock(spec=ops.PebbleReadyEvent))


def test__on_jenkins_agent_k8s_pebble_ready(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a mocked server functions.
    act: when _on_jenkins_agent_k8s_pebble_ready is called.
    assert: the charm is in ActiveStatus.
    """
    harness.set_can_connect(state.State.jenkins_agent_service_name, True)
    harness.begin()
    charm = typing.cast(JenkinsAgentCharm, harness.charm)
    charm.state.agent_relation_credentials = server.Credentials(
        address="test", secret=secrets.token_hex(16)
    )
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        MagicMock(spec=server.download_jenkins_agent),
    )

    charm._on_jenkins_agent_k8s_pebble_ready(MagicMock(spec=ops.PebbleReadyEvent))

    assert charm.unit.status.name == ACTIVE_STATUS_NAME
