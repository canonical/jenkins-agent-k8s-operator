# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s agent relation handling tests.

These tests exercise reconciliation paths that are specific to the
agent relation (credentials changed, incomplete data, download errors).
All events now funnel to _on_reconcile, so the event type no longer
matters — what matters is the state (credentials, container, server).
"""

# Need access to protected functions for testing
# pylint:disable=protected-access

import typing
import unittest.mock

import ops
import ops.testing
import pytest

import pebble
import server
import state
from charm import JenkinsAgentCharm

from .constants import ACTIVE_STATUS_NAME


@pytest.mark.parametrize(
    "creds_changed",
    [
        pytest.param(False, id="no_change"),
        pytest.param(True, id="credentials_changed"),
    ],
)
def test_reconcile_service_running(
    harness: ops.testing.Harness,
    monkeypatch: pytest.MonkeyPatch,
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
    creds_changed: bool,
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
    arrange: given an agent running with old credentials and server not reachable.
    act: when reconcile is triggered with new server URL.
    assert: RuntimeError is raised so Juju retries the event.
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
    with pytest.raises(RuntimeError):
        jenkins_charm._on_reconcile(mock_event)


def test_reconcile_incomplete_relation_data(
    harness: ops.testing.Harness,
    get_mock_relation_changed_event: typing.Callable[[str], ops.RelationChangedEvent],
):
    """
    arrange: given an agent with incomplete relation data (missing secret).
    act: when reconcile is triggered.
    assert: charm falls into BlockedStatus.
    """
    mock_event = get_mock_relation_changed_event(state.AGENT_RELATION)
    harness.set_can_connect("jenkins-agent-k8s", True)
    relation_id = harness.add_relation(state.AGENT_RELATION, remote_app="jenkins")
    harness.add_relation_unit(relation_id, "jenkins/0")
    harness.update_relation_data(relation_id, "jenkins/0", {"url": "test"})
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == "blocked"


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
    assert: AgentJarDownloadError is propagated so Juju retries the event.
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
    with pytest.raises(server.AgentJarDownloadError):
        jenkins_charm._on_reconcile(mock_event)


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
