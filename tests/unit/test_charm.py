# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-k8s-agent charm module tests."""

import typing
import unittest.mock

import ops
import ops.testing
import pytest

import server
import state
from charm import JenkinsAgentCharm


def test___init___invalid_state(
    harness: ops.testing.Harness, monkeypatch: pytest.MonkeyPatch, raise_exception: typing.Callable
):
    """
    arrange: given a monkeypatched State.from_charm that rasies an InvalidState Error.
    act: when the JenkinsAgentCharm is initialized.
    assert: The agent falls into BlockedStatus.
    """
    monkeypatch.setattr(
        state.State,
        "from_charm",
        lambda *_args, **_kwargs: raise_exception(state.InvalidStateError),
    )
    harness.begin_with_initial_hooks()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)

    assert jenkins_charm.unit.status.name == ops.BlockedStatus.name


def test__register_agent_from_config_container_not_ready(harness: ops.testing.Harness):
    """
    arrange: given a charm with a workload container that is not ready yet.
    act: when _register_agent_from_config is called.
    assert: the event is deferred.
    """
    harness.set_can_connect("jenkins-k8s-agent", False)
    harness.begin()
    mock_event = unittest.mock.MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._register_agent_from_config(mock_event)

    mock_event.defer.assert_called_once()


def test__register_agent_from_config_no_config_state(harness: ops.testing.Harness):
    """
    arrange: given a charm with no configured state nor relation.
    act: when _register_agent_from_config is called.
    assert: the unit falls into BlockedStatus.
    """
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()
    mock_event = unittest.mock.MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._register_agent_from_config(mock_event)

    assert jenkins_charm.unit.status.name == ops.BlockedStatus.name


def test__register_agent_from_config_use_relation(harness: ops.testing.Harness):
    """
    arrange: given a charm with an agent relation but no configured state.
    act: when _register_agent_from_config is called.
    assert: the nothing happens since agent observer should be handling the relation.
    """
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.begin()
    mock_event = unittest.mock.MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._register_agent_from_config(mock_event)

    mock_event.defer.assert_not_called()


def test__register_agent_from_config_download_agent_error(
    monkeypatch: pytest.MonkeyPatch,
    raise_exception: typing.Callable,
    harness: ops.testing.Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched download_jenkins_agent that raises an excetion.
    act: when _register_agent_from_config is called.
    assert: unit falls into BlockedStatus.
    """
    monkeypatch.setattr(
        server,
        "download_jenkins_agent",
        lambda *_args, **_kwargs: raise_exception(server.AgentJarDownloadError),
    )
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.update_config(config)
    harness.begin()
    mock_event = unittest.mock.MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._register_agent_from_config(mock_event)

    assert jenkins_charm.unit.status.name == ops.BlockedStatus.name


def test__register_agent_from_config_no_valid_credentials(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched validate_credentials that returns false.
    act: when _register_agent_from_config is called.
    assert: unit falls into BlockedStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: False)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.update_config(config)
    harness.begin()
    mock_event = unittest.mock.MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._register_agent_from_config(mock_event)

    assert jenkins_charm.unit.status.name == ops.BlockedStatus.name


def test__register_agent_from_config(
    monkeypatch: pytest.MonkeyPatch,
    harness: ops.testing.Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched server functions that returns passing values.
    act: when _register_agent_from_config is called.
    assert: unit falls into ActiveStatus.
    """
    monkeypatch.setattr(server, "download_jenkins_agent", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server, "validate_credentials", lambda *_args, **_kwargs: True)
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.update_config(config)
    harness.begin()
    mock_event = unittest.mock.MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._register_agent_from_config(mock_event)

    assert jenkins_charm.unit.status.name == ops.ActiveStatus.name
