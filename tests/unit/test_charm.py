# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s charm reconciliation tests.

All events now funnel to a single _on_reconcile handler.  The event type is
irrelevant once inside the handler — what matters is the state derived from
config, relation data, and container readiness.  Tests are organized by the
reconciliation gate they exercise rather than by the event that triggers it.
"""

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

from .constants import ACTIVE_STATUS_NAME, BLOCKED_STATUS_NAME


def test___init___invalid_state(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, raise_exception: typing.Callable
):
    """
    arrange: given a monkeypatched State.from_charm that raises InvalidStateError.
    act: when the JenkinsAgentCharm is initialized.
    assert: The unit falls into BlockedStatus with the error message.
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


@pytest.mark.parametrize(
    "event_cls",
    [
        pytest.param(ops.RelationJoinedEvent, id="relation_joined"),
        pytest.param(ops.RelationDepartedEvent, id="relation_departed"),
        pytest.param(ops.ConfigChangedEvent, id="config_changed"),
        pytest.param(ops.PebbleReadyEvent, id="pebble_ready"),
    ],
)
def test_reconcile_invalid_state(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    raise_exception: typing.Callable,
    event_cls: typing.Type[ops.EventBase],
):
    """
    arrange: given any event type that triggers _on_reconcile and a State.from_charm
             that raises InvalidStateError.
    act: when the reconcile handler runs.
    assert: the unit always falls into BlockedStatus regardless of event type.
    """
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    invalid_state_message = "Bad state"
    monkeypatch.setattr(
        state.State,
        "from_charm",
        lambda *_args, **_kwargs: raise_exception(state.InvalidStateError(invalid_state_message)),
    )

    if issubclass(event_cls, ops.RelationEvent):
        relation_id = harness.add_relation("agent", "jenkins-k8s")
        harness.add_relation_unit(relation_id, "jenkins-k8s/0")
        mock_event = MagicMock(spec=event_cls)
        mock_event.relation = harness.model.get_relation("agent")
    else:
        mock_event = MagicMock(spec=event_cls)

    jenkins_charm._on_reconcile(mock_event)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == invalid_state_message


def test_reconcile_no_config_no_relation(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a charm with no config, no relation, and a running agent
             (ready file exists).
    act: when _on_reconcile is called.
    assert: the running agent is NOT stopped (charm only blocks; operator
            handles workload lifecycle), and the unit falls into BlockedStatus.
    """
    import pebble as pebble_mod

    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    mock_stop = MagicMock()
    monkeypatch.setattr(pebble_mod.PebbleService, "stop_agent", mock_stop)

    # Simulate agent ready file existing.
    container = harness.charm.unit.get_container("jenkins-agent-k8s")
    container.make_dir(str(server.AGENT_READY_PATH.parent), make_parents=True)
    container.push(str(server.AGENT_READY_PATH), "ready")

    mock_event = MagicMock(spec=ops.HookEvent)
    jenkins_charm._on_reconcile(mock_event)

    mock_stop.assert_not_called()
    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert (
        jenkins_charm.unit.status.message == "Credentials not available from config or relation."
    )


def test_reconcile_publishes_databag_on_join(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a charm with a valid relation but empty local databag.
    act: when reconcile fires with relation source.
    assert: agent metadata is written to the relation databag.
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
    mock_event = MagicMock(spec=ops.RelationJoinedEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    relation = harness.model.get_relation(state.AGENT_RELATION)
    assert relation is not None
    unit_data = dict(relation.data[jenkins_charm.unit])
    assert "executors" in unit_data
    assert "name" in unit_data


def test_reconcile_skips_databag_write_when_populated(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given a charm with a relation whose databag already has correct metadata.
    act: when reconcile fires again (idempotent).
    assert: databag is not re-written, agent stays active.
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

    # First reconcile — publishes databag and starts agent.
    mock_event = MagicMock(spec=ops.RelationJoinedEvent)
    jenkins_charm._on_reconcile(mock_event)

    # Simulate agent is now running with correct credentials.
    container = harness.charm.unit.get_container("jenkins-agent-k8s")
    container.make_dir(str(server.AGENT_READY_PATH.parent), make_parents=True)
    container.push(str(server.AGENT_READY_PATH), "ready")

    # Second reconcile — should short-circuit at Gate 2 (agent up-to-date).
    mock_event2 = MagicMock(spec=ops.HookEvent)
    jenkins_charm._on_reconcile(mock_event2)

    assert jenkins_charm.unit.status.name == ACTIVE_STATUS_NAME


@pytest.mark.parametrize(
    "event_cls",
    [
        pytest.param(ops.HookEvent, id="generic_event"),
        pytest.param(ops.PebbleReadyEvent, id="pebble_ready"),
    ],
)
def test_reconcile_container_not_ready(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    event_cls: typing.Type[ops.EventBase],
):
    """
    arrange: given a charm with a workload container that is not yet ready.
    act: when _on_reconcile is called with any event type.
    assert: Gate 1 short-circuits before any server/pebble work.
    """
    harness.set_can_connect("jenkins-agent-k8s", False)
    mock_server_is_ready = MagicMock()
    monkeypatch.setattr(server, "server_is_ready", mock_server_is_ready)
    harness.begin()
    mock_event = MagicMock(spec=event_cls)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    jenkins_charm._on_reconcile(mock_event)

    mock_server_is_ready.assert_not_called()


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
    assert (
        jenkins_charm.unit.status.message
        == "Please remove either configuration or agent relation."
    )


def test_reconcile_config_download_agent_error(
    monkeypatch: pytest.MonkeyPatch,
    raise_exception: typing.Callable,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched download_jenkins_agent that raises.
    act: when _on_reconcile is called.
    assert: AgentJarDownloadError is propagated so Juju retries.
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
    with pytest.raises(server.AgentJarDownloadError):
        jenkins_charm._on_reconcile(mock_event)


def test_reconcile_config_no_valid_credentials(
    monkeypatch: pytest.MonkeyPatch,
    harness: Harness,
    config: typing.Dict[str, str],
):
    """
    arrange: given a charm with monkeypatched validate_credentials that returns False.
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
    arrange: given a charm with monkeypatched server functions that return passing values.
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
    arrange: given a charm with monkeypatched server functions that return passing values.
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
    assert: RuntimeError is raised so Juju retries the event.
    """
    monkeypatch.setattr(server, "server_is_ready", lambda *_args, **_kwargs: False)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.update_config(config)
    harness.begin()
    mock_event = MagicMock(spec=ops.HookEvent)

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    with pytest.raises(RuntimeError):
        jenkins_charm._on_reconcile(mock_event)


def test_ensure_databag_published_no_relation(harness: Harness):
    """
    arrange: given a charm with no agent relation.
    act: when _ensure_databag_published is called directly.
    assert: a RuntimeError is raised because the relation is missing.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    mock_state = MagicMock()

    with pytest.raises(RuntimeError):
        jenkins_charm._ensure_databag_published(mock_state)


def test_reconcile_from_config_missing_state(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a charm where _reconcile_from_config is called with jenkins_config=None.
    act: when _reconcile_from_config is called.
    assert: unit falls into BlockedStatus with an internal error message.
    """
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()
    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    container = jenkins_charm.unit.get_container("jenkins-agent-k8s")
    mock_pebble = MagicMock()
    mock_state = MagicMock()
    mock_state.jenkins_config = None

    jenkins_charm._reconcile_from_config(mock_state, mock_pebble, container)

    assert jenkins_charm.unit.status.name == BLOCKED_STATUS_NAME
    assert jenkins_charm.unit.status.message == "Internal error: config state missing."
