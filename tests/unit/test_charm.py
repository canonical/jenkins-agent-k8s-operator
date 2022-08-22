# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

# Disable since testing relies on checking private state of the charm.
# pylint: disable=protected-access
# Disable since parametrised testing sometimes requires many arguments.
# pylint: disable=too-many-arguments

"""Unit tests for the charm."""

import logging
import os
from unittest import mock

import pytest
from ops.model import ActiveStatus, BlockedStatus, Container, MaintenanceStatus
from ops.testing import Harness

from src.charm import JenkinsAgentCharm

from . import types


def test__get_env_config_initial(harness: Harness[JenkinsAgentCharm]):
    """
    arrange: given charm in its initial state
    act: when the environment variables for the charm are generated
    assert: then the environment is empty.
    """
    env_config = harness.charm._get_env_config()

    assert env_config == {
        "JENKINS_AGENTS": "",
        "JENKINS_TOKENS": "",
        "JENKINS_URL": "",
    }


def test__get_env_config_config(harness: Harness[JenkinsAgentCharm]):
    """
    arrange: given charm in its initial state except that the configuration has been set
    act: when the environment variables for the charm are generated
    assert: then the environment contains the data from the configuration.
    """
    jenkins_url = "http://test"
    jenkins_agent_name = "agent"
    jenkins_agent_token = "token"
    harness.update_config(
        {
            "jenkins_url": jenkins_url,
            "jenkins_agent_name": jenkins_agent_name,
            "jenkins_agent_token": jenkins_agent_token,
        }
    )

    env_config = harness.charm._get_env_config()

    assert env_config == {
        "JENKINS_AGENTS": jenkins_agent_name,
        "JENKINS_TOKENS": jenkins_agent_token,
        "JENKINS_URL": jenkins_url,
    }


def test__get_env_config_relation(harness: Harness[JenkinsAgentCharm]):
    """
    arrange: given charm in its initial state except that relation data has been set
    act: when the environment variables for the charm are generated
    assert: then the environment contains the data from the relation.
    """
    jenkins_url = "http://test"
    harness.charm._stored.relation_configured = True
    harness.charm._stored.jenkins_url = jenkins_url
    agent_name = "agent 0"
    harness.charm._stored.relation_agent_name = agent_name
    agent_token = "token 0"
    harness.charm._stored.relation_agent_token = agent_token

    env_config = harness.charm._get_env_config()

    assert env_config == {
        "JENKINS_AGENTS": agent_name,
        "JENKINS_TOKENS": agent_token,
        "JENKINS_URL": jenkins_url,
    }


def test__get_env_config_config_relation(harness: Harness[JenkinsAgentCharm]):
    """
    arrange: given charm in its initial state except that the configuration and relation data
        has been set
    act: when the environment variables for the charm are generated
    assert: then the environment contains the data from the relation.
    """
    # Set the configuration
    config_jenkins_url = "http://test_config"
    config_jenkins_agent_name = "agent config"
    config_jenkins_agent_token = "token config"
    harness.update_config(
        {
            "jenkins_url": config_jenkins_url,
            "jenkins_agent_name": config_jenkins_agent_name,
            "jenkins_agent_token": config_jenkins_agent_token,
        }
    )
    # Set the relation
    relation_jenkins_url = "http://test_relation"
    relation_jenkins_agent_name = "agent relation"
    relation_jenkins_agent_token = "token relation"
    harness.charm._stored.relation_configured = True
    harness.charm._stored.jenkins_url = relation_jenkins_url
    harness.charm._stored.relation_agent_name = relation_jenkins_agent_name
    harness.charm._stored.relation_agent_token = relation_jenkins_agent_token

    env_config = harness.charm._get_env_config()

    assert env_config == {
        "JENKINS_AGENTS": relation_jenkins_agent_name,
        "JENKINS_TOKENS": relation_jenkins_agent_token,
        "JENKINS_URL": relation_jenkins_url,
    }


def test_config_changed_invalid(harness_pebble_ready: Harness[JenkinsAgentCharm]):
    """
    arrange: given charm in its initial state
    act: when the config_changed event occurs
    assert: then the charm enters the blocked status with message that required configuration is
        missing.
    """
    harness_pebble_ready.charm.on.config_changed.emit()

    assert isinstance(harness_pebble_ready.model.unit.status, BlockedStatus)
    assert "jenkins_agent_name" in harness_pebble_ready.model.unit.status.message
    assert "jenkins_agent_token" in harness_pebble_ready.model.unit.status.message


def test_config_changed(
    harness_pebble_ready: Harness[JenkinsAgentCharm],
    monkeypatch: pytest.MonkeyPatch,
    valid_config,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: given charm in its initial state with valid configuration
    act: when the config_changed event occurs
    assert: then the charm is in the active status, the container has the jenkins-agent service and
        has been replanned and a log message indicating a layer has been added is written.
    """
    harness_pebble_ready.update_config(valid_config)
    # Mock the replan_services function on the container
    container: Container = harness_pebble_ready.model.unit.get_container(
        harness_pebble_ready.charm.service_name
    )
    mock_replan_services = mock.MagicMock()
    monkeypatch.setattr(container.pebble, "replan_services", mock_replan_services)

    caplog.set_level(logging.DEBUG)
    harness_pebble_ready.charm.on.config_changed.emit()

    assert isinstance(harness_pebble_ready.model.unit.status, ActiveStatus)
    assert harness_pebble_ready.charm.service_name in container.get_plan().services
    mock_replan_services.assert_called_once_with()
    assert "add_layer" in caplog.text.lower()


def test_config_changed_pebble_not_ready(
    harness: Harness[JenkinsAgentCharm], valid_config, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given charm where the pebble is not ready state with valid configuration
    act: when the config_changed event occurs
    assert: then the unit stayis in maintenance status and the container is not replanned.
    """
    harness.update_config(valid_config)
    # Mock the replan_services function on the container
    container: Container = harness.model.unit.get_container(harness.charm.service_name)
    mock_replan_services = mock.MagicMock()
    monkeypatch.setattr(container.pebble, "replan_services", mock_replan_services)

    harness.charm.on.config_changed.emit()

    assert isinstance(harness.model.unit.status, MaintenanceStatus)
    mock_replan_services.assert_not_called()


def test_config_changed_no_change(
    harness_pebble_ready: Harness[JenkinsAgentCharm],
    valid_config,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given charm in active state with valid configuration
    act: when the config_changed event occurs
    assert: the charm stays in the active status, the container is not replanned and a log message
        indicating unchanged configuration is written.
    """
    # Get container into active state
    harness_pebble_ready.update_config(valid_config)
    harness_pebble_ready.charm.on.config_changed.emit()
    # Mock the replan_services function on the container
    container: Container = harness_pebble_ready.model.unit.get_container(
        harness_pebble_ready.charm.service_name
    )
    mock_replan_services = mock.MagicMock()
    monkeypatch.setattr(container.pebble, "replan_services", mock_replan_services)

    caplog.set_level(logging.DEBUG)
    harness_pebble_ready.charm.on.config_changed.emit()

    assert isinstance(harness_pebble_ready.model.unit.status, ActiveStatus)
    mock_replan_services.assert_not_called()
    assert "unchanged" in caplog.text.lower()


@pytest.mark.parametrize(
    "relation_configured, agent_tokens, config, expected_validity, expected_message_contents, "
    "expected_not_in_message_contents",
    [
        pytest.param(
            False,
            [],
            {"jenkins_url": "", "jenkins_agent_name": "", "jenkins_agent_token": ""},
            False,
            ["jenkins_url", "jenkins_agent_name", "jenkins_agent_token"],
            [],
            id="relation_configured not set and configuration empty",
        ),
        pytest.param(
            True,
            ["token"],
            {"jenkins_url": "", "jenkins_agent_name": "", "jenkins_agent_token": ""},
            True,
            [],
            [],
            id="relation_configured set and configuration empty",
        ),
        pytest.param(
            False,
            [],
            {"jenkins_url": "http://test", "jenkins_agent_name": "", "jenkins_agent_token": ""},
            False,
            ["jenkins_agent_name", "jenkins_agent_token"],
            ["jenkins_url"],
            id="relation_configured not set and configuration empty except jenkins_url set",
        ),
        pytest.param(
            False,
            [],
            {"jenkins_url": "", "jenkins_agent_name": "agent 1", "jenkins_agent_token": "token 1"},
            False,
            ["jenkins_url"],
            ["jenkins_agent_name", "jenkins_agent_token"],
            id="relation_configured not set and configuration empty except jenkins_agent_name and "
            "jenkins_agent_token set",
        ),
        pytest.param(
            False,
            [],
            {
                "jenkins_url": "http://test",
                "jenkins_agent_name": "agent 1",
                "jenkins_agent_token": "token 1",
            },
            True,
            [],
            [],
            id="relation_configured not set and configuration valid",
        ),
    ],
)
def test__is_valid_config(
    harness: Harness[JenkinsAgentCharm],
    relation_configured,
    agent_tokens: list[str],
    config,
    expected_validity: bool,
    expected_message_contents: list[str],
    expected_not_in_message_contents: list[str],
):
    """
    arrange: given charm with the given agent_tokens and configuration set
    act: when _is_valid_config is called
    assert: then the expected configuration validity and message is returned.
    """
    harness.charm._stored.relation_configured = relation_configured
    harness.charm._stored.relation_agent_tokens = agent_tokens
    harness.update_config(config)

    validity, message = harness.charm._is_valid_config()

    assert validity == expected_validity
    for expected_message_content in expected_message_contents:
        assert expected_message_content in message
    for expected_not_in_message_content in expected_not_in_message_contents:
        assert expected_not_in_message_content not in message


def test_on_agent_relation_joined(
    harness: Harness[JenkinsAgentCharm],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """
    arrange: given charm in its initial state
    act: when the slave_relation_joined event occurs
    assert: then the agent sets the executors, labels and slave hosts relation data and writes a
        note to the logs.
    """
    # Mock uname and CPU count
    mock_cpu_count = mock.MagicMock()
    cpu_count = 8
    mock_cpu_count.return_value = cpu_count
    monkeypatch.setattr(os, "cpu_count", mock_cpu_count)
    mock_uname = mock.MagicMock()
    machine_architecture = "x86_64"
    mock_uname.return_value.machine = machine_architecture
    monkeypatch.setattr(os, "uname", mock_uname)

    caplog.set_level(logging.INFO)
    harness.enable_hooks()
    relation_id = harness.add_relation(relation_name="slave", remote_app="jenkins")
    harness.add_relation_unit(relation_id=relation_id, remote_unit_name=harness.charm.unit.name)

    assert harness.get_relation_data(
        relation_id=relation_id, app_or_unit=harness.charm.unit.name
    ) == {
        "executors": str(cpu_count),
        "labels": machine_architecture,
        "slavehost": harness.charm._stored.relation_agent_name,
    }
    assert "relation" in caplog.text.lower()
    assert "joined" in caplog.text.lower()


def test_on_agent_relation_joined_labels(
    harness: Harness[JenkinsAgentCharm], monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: given charm in its initial state with labels configured
    act: when the slave_relation_joined occurs
    assert: then the agent sets the labels based on the configuration.
    """
    labels = "label 1,label 2"
    harness.update_config({"jenkins_agent_labels": labels})

    # Mock CPU count and uname
    monkeypatch.setattr(os, "uname", mock.MagicMock())
    monkeypatch.setattr(os, "cpu_count", mock.MagicMock())

    harness.enable_hooks()
    relation_id = harness.add_relation(relation_name="slave", remote_app="jenkins")
    unit_name = "jenkins-agent-k8s/0"
    harness.add_relation_unit(relation_id=relation_id, remote_unit_name=unit_name)

    assert harness.get_relation_data(relation_id, unit_name)["labels"] == labels


def test_on_agent_relation_changed_jenkins_url_missing(
    harness: Harness[JenkinsAgentCharm],
    caplog: pytest.LogCaptureFixture,
    charm_with_jenkins_relation: types.CharmWithJenkinsRelation,
):
    """
    arrange: given charm with relation to jenkins
    act: when the relation data is updated without the jenkins url
    assert: the unit stays in active status and a warning is written to the logs.
    """
    # Update relation data
    caplog.set_level(logging.INFO)
    harness.update_relation_data(
        relation_id=charm_with_jenkins_relation.relation_id,
        app_or_unit=charm_with_jenkins_relation.remote_unit_name,
        key_values={"secret": "relation token"},
    )

    assert harness.charm._stored.jenkins_url is None
    assert harness.charm._stored.relation_agent_token is None
    assert harness.charm._stored.relation_agent_name == harness.charm._stored.relation_agent_name
    assert isinstance(harness.model.unit.status, ActiveStatus)
    assert "expected 'url'" in caplog.text.lower()
    assert "skipping setup" in caplog.text.lower()


def test_on_agent_relation_changed_secret_missing(
    harness: Harness[JenkinsAgentCharm],
    caplog: pytest.LogCaptureFixture,
    charm_with_jenkins_relation: types.CharmWithJenkinsRelation,
):
    """
    arrange: given charm with relation to jenkins
    act: when the relation data is updated without the secret
    assert: the unit stays in active status and a warning is written to the logs.
    """
    # Update relation data
    caplog.set_level(logging.INFO)
    harness.update_relation_data(
        relation_id=charm_with_jenkins_relation.relation_id,
        app_or_unit=charm_with_jenkins_relation.remote_unit_name,
        key_values={"url": "http://relation"},
    )

    assert harness.charm._stored.jenkins_url is None
    assert harness.charm._stored.relation_agent_token is None
    assert harness.charm._stored.relation_agent_name == harness.charm._stored.relation_agent_name
    assert isinstance(harness.model.unit.status, ActiveStatus)
    assert "expected 'secret'" in caplog.text.lower()
    assert "skipping setup" in caplog.text.lower()


def test_on_agent_relation_changed(
    harness: Harness[JenkinsAgentCharm],
    caplog: pytest.LogCaptureFixture,
    charm_with_jenkins_relation: types.CharmWithJenkinsRelation,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given charm with relation to jenkins
    act: when the relation data is updated
    assert: then the relation data is stored on the charm, the unit enters maintenance status,
        emits the config_changed event and writes a note to the logs.
    """
    # Mock config_changed hook
    mock_config_changed = mock.MagicMock()
    monkeypatch.setattr(harness.charm.on, "config_changed", mock_config_changed)

    # Update relation data
    caplog.set_level(logging.INFO)
    relation_jenkins_url = "http://relation"
    relation_secret = "relation token"
    harness.update_relation_data(
        relation_id=charm_with_jenkins_relation.relation_id,
        app_or_unit=charm_with_jenkins_relation.remote_unit_name,
        key_values={"url": relation_jenkins_url, "secret": relation_secret},
    )

    assert harness.charm._stored.relation_configured is True
    assert harness.charm._stored.jenkins_url == relation_jenkins_url
    assert harness.charm._stored.relation_agent_token == relation_secret
    assert harness.charm._stored.relation_agent_name == harness.charm._stored.relation_agent_name
    mock_config_changed.emit.assert_called_once_with()
    assert isinstance(harness.model.unit.status, MaintenanceStatus)
    assert "configuring" in harness.model.unit.status.message.lower()
    assert "relation" in caplog.text.lower()
    assert "changed" in caplog.text.lower()


def test_on_agent_relation_changed_new_agent_name(
    harness: Harness[JenkinsAgentCharm],
    charm_with_jenkins_relation: types.CharmWithJenkinsRelation,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given charm with relation to jenkins and an existing agent
    act: when the relation data is updated
    assert: then a new agent is stored.
    """
    harness.charm._stored.relation_agent_name = harness.charm._stored.relation_agent_name
    # Mock config_changed hook
    monkeypatch.setattr(harness.charm.on, "config_changed", mock.MagicMock())

    # Update relation data
    harness.update_relation_data(
        relation_id=charm_with_jenkins_relation.relation_id,
        app_or_unit=charm_with_jenkins_relation.remote_unit_name,
        key_values={"url": "http://relation", "secret": "relation token"},
    )

    assert harness.charm._stored.relation_agent_name == harness.charm._stored.relation_agent_name


def test_on_agent_relation_changed_jenkins_url_configured(
    harness: Harness[JenkinsAgentCharm],
    valid_config,
    caplog: pytest.LogCaptureFixture,
    charm_with_jenkins_relation: types.CharmWithJenkinsRelation,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: given charm with relation to jenkins and the jenkins_url configuration set
    act: when the relation data is updated
    assert: then the relation data is stored on the charm, the unit goes into active status, emits
        the config_changed event and writes a warning to the logs.
    """
    harness.update_config(valid_config)
    # Mock config_changed hook
    mock_config_changed = mock.MagicMock()
    monkeypatch.setattr(harness.charm.on, "config_changed", mock_config_changed)

    # Update relation data
    caplog.set_level(logging.WARNING)
    relation_jenkins_url = "http://relation"
    relation_secret = "relation token"
    harness.update_relation_data(
        relation_id=charm_with_jenkins_relation.relation_id,
        app_or_unit=charm_with_jenkins_relation.remote_unit_name,
        key_values={"url": relation_jenkins_url, "secret": relation_secret},
    )

    assert harness.charm._stored.jenkins_url == relation_jenkins_url
    assert harness.charm._stored.relation_agent_token == relation_secret
    assert harness.charm._stored.relation_agent_name == harness.charm._stored.relation_agent_name
    mock_config_changed.emit.assert_called_once_with()
    assert isinstance(harness.model.unit.status, MaintenanceStatus)
    assert "'jenkins_url'" in caplog.text.lower()
