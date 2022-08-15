# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

from unittest import mock
import logging
import os

import pytest
from ops import model
from ops import testing

from charm import JenkinsAgentCharm

SERVICE_NAME = "jenkins-agent"

CONFIG_DEFAULT = {
    "image": "jenkins-agent-operator",
    "jenkins_url": "",
    "jenkins_agent_name": "",
    "jenkins_agent_token": "",
    "jenkins_agent_label": "",
}

CONFIG_ONE_AGENT = {
    "jenkins_url": "http://test",
    "jenkins_agent_name": "agent-one",
    "jenkins_agent_token": "token-one",
}

CONFIG_ONE_AGENT_CUSTOM_IMAGE = {
    "image": "image-name",
    "jenkins_url": "http://test",
    "jenkins_agent_name": "agent-one",
    "jenkins_agent_token": "token-one",
}

ENV_INITIAL = {'JENKINS_AGENTS': '', 'JENKINS_TOKENS': '', 'JENKINS_URL': ''}

ENV_ONE_AGENT = {
    'JENKINS_AGENTS': 'agent-one',
    'JENKINS_TOKENS': 'token-one',
    'JENKINS_URL': 'http://test',
}

SPEC_EXPECTED = {
    'containers': [
        {
            'config': {
                'JENKINS_AGENTS': 'agent-one',
                'JENKINS_TOKENS': 'token-one',
                'JENKINS_URL': 'http://test',
            },
            'imageDetails': {'imagePath': 'image-name'},
            'name': 'jenkins-agent',
            'readinessProbe': {'exec': {'command': ['/bin/cat', '/var/lib/jenkins/agents/.ready']}},
        }
    ]
}


def test__get_env_config_initial(harness: testing.Harness[JenkinsAgentCharm]):
    """arrange: given charm in its initial state
    act: when the environment variables for the charm are generated
    assert: then the environment is empty.
    """
    env_config = harness.charm._get_env_config()

    assert env_config == {
        'JENKINS_AGENTS': '',
        'JENKINS_TOKENS': '',
        'JENKINS_URL': '',
    }


def test__get_env_config_config(harness: testing.Harness[JenkinsAgentCharm]):
    """arrange: given charm in its initial state except that the configuration has been set
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
        'JENKINS_AGENTS': jenkins_agent_name,
        'JENKINS_TOKENS': jenkins_agent_token,
        'JENKINS_URL': jenkins_url,
    }


@pytest.mark.parametrize(
    "agents, expected_jenkins_agent_name, tokens, expected_jenkins_agent_token",
    [
        pytest.param([], "", [], "", id="empty"),
        pytest.param(["agent"], "agent", ["token"], "token", id="single"),
        pytest.param(
            ["agent 1", "agent 2"],
            "agent 1:agent 2",
            ["token 1", "token 2"],
            "token 1:token 2",
            id="multiple",
        ),
    ],
)
def test__get_env_config_relation(
    harness: testing.Harness[JenkinsAgentCharm],
    agents: list[str],
    expected_jenkins_agent_name: str,
    tokens: list[str],
    expected_jenkins_agent_token: str,
):
    """arrange: given charm in its initial state except that relation data has been set
    act: when the environment variables for the charm are generated
    assert: then the environment contains the data from the relation.
    """
    jenkins_url = "http://test"
    harness.charm._stored.jenkins_url = jenkins_url
    harness.charm._stored.agents = agents
    harness.charm._stored.agent_tokens = tokens

    env_config = harness.charm._get_env_config()

    assert env_config == {
        'JENKINS_AGENTS': expected_jenkins_agent_name,
        'JENKINS_TOKENS': expected_jenkins_agent_token,
        'JENKINS_URL': jenkins_url,
    }


def test__get_env_config_config_relation(harness: testing.Harness[JenkinsAgentCharm]):
    """arrange: given charm in its initial state except that the configuration and relation data
        has been set
    act: when the environment variables for the charm are generated
    assert: then the environment contains the data from the relation.
    """
    # Set the configuraton
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
    harness.charm._stored.jenkins_url = relation_jenkins_url
    harness.charm._stored.agents = [relation_jenkins_agent_name]
    harness.charm._stored.agent_tokens = [relation_jenkins_agent_token]

    env_config = harness.charm._get_env_config()

    assert env_config == {
        'JENKINS_AGENTS': relation_jenkins_agent_name,
        'JENKINS_TOKENS': relation_jenkins_agent_token,
        'JENKINS_URL': relation_jenkins_url,
    }


def test_config_changed_invalid(harness: testing.Harness[JenkinsAgentCharm]):
    """arrange: given charm in its initial state
    act: when the config_changed event occurs
    assert: the charm enters the blocked status with message that required configuration is missing
    """
    harness.charm.on.config_changed.emit()

    assert isinstance(harness.model.unit.status, model.BlockedStatus)
    assert "jenkins_agent_name" in harness.model.unit.status.message
    assert "jenkins_agent_token" in harness.model.unit.status.message


def test_config_changed(
    harness: testing.Harness[JenkinsAgentCharm], valid_config, caplog: pytest.LogCaptureFixture
):
    """arrange: given charm in its initial state with valid configuration
    act: when the config_changed event occurs
    assert: the charm is in the active status, the container has the jenkins-agent service and has
        been restarted and a log message indicating a layer has been added is written.
    """
    harness.update_config(valid_config)
    # Mock the restart function on the container
    container: model.Container = harness.model.unit.get_container(harness.charm.service_name)
    container.restart = mock.MagicMock()

    caplog.set_level(logging.DEBUG)
    harness.charm.on.config_changed.emit()

    assert isinstance(harness.model.unit.status, model.ActiveStatus)
    assert harness.charm.service_name in container.get_plan().services
    container.restart.assert_called_once_with(harness.charm.service_name)
    assert "add_layer" in caplog.text


def test_config_changed_no_change(
    harness: testing.Harness[JenkinsAgentCharm], valid_config, caplog: pytest.LogCaptureFixture
):
    """arrange: given charm in active state with valid configuration
    act: when the config_changed event occurs
    assert: the charm stays in the active status, the container is not restarted and a log message
        indicating unchaged configuration is written.
    """
    # Get container into active state
    harness.update_config(valid_config)
    harness.charm.on.config_changed.emit()
    # Mock the restart function on the container
    container: model.Container = harness.model.unit.get_container(harness.charm.service_name)
    container.restart = mock.MagicMock()

    caplog.set_level(logging.DEBUG)
    harness.charm.on.config_changed.emit()

    assert isinstance(harness.model.unit.status, model.ActiveStatus)
    container.restart.assert_not_called()
    assert "unchanged" in caplog.text


@pytest.mark.parametrize(
    "agent_tokens, config, expected_validity, expected_message_contents, "
    "expected_not_in_message_contents",
    [
        pytest.param(
            [],
            {"jenkins_url": "", "jenkins_agent_name": "", "jenkins_agent_token": ""},
            False,
            ("jenkins_url", "jenkins_agent_name", "jenkins_agent_token"),
            (),
            id="agent_tokens not set and configuration empty",
        ),
        pytest.param(
            ["token"],
            {"jenkins_url": "", "jenkins_agent_name": "", "jenkins_agent_token": ""},
            True,
            (),
            (),
            id="agent_tokens set and configuration empty",
        ),
        pytest.param(
            [],
            {"jenkins_url": "http://test", "jenkins_agent_name": "", "jenkins_agent_token": ""},
            False,
            ("jenkins_agent_name", "jenkins_agent_token"),
            ("jenkins_url",),
            id="agent_tokens not set and configuration empty except jenkins_url set",
        ),
        pytest.param(
            [],
            {"jenkins_url": "", "jenkins_agent_name": "agent 1", "jenkins_agent_token": "token 1"},
            False,
            ("jenkins_url",),
            ("jenkins_agent_name", "jenkins_agent_token"),
            id="agent_tokens not set and configuration empty except jenkins_agent_name and "
            "jenkins_agent_token set",
        ),
        pytest.param(
            [],
            {
                "jenkins_url": "http://test",
                "jenkins_agent_name": "agent 1",
                "jenkins_agent_token": "token 1",
            },
            True,
            (),
            (),
            id="agent_tokens not set and configuration valid",
        ),
    ],
)
def test__is_valid_config(
    harness: testing.Harness[JenkinsAgentCharm],
    agent_tokens: list[str],
    config,
    expected_validity: bool,
    expected_message_contents: tuple[str, ...],
    expected_not_in_message_contents: tuple[str, ...],
):
    """arrange: given charm with the given agent_tokens and configuration set
    act: when _is_valid_config is called
    assert: then the expected configuration validity and message is returned.
    """
    harness.charm._stored.agent_tokens = agent_tokens
    harness.update_config(config)

    validity, message = harness.charm._is_valid_config()

    assert validity == expected_validity
    if validity:
        assert message is None
        return
    for expected_message_content in expected_message_contents:
        assert expected_message_content in message
    for expected_not_in_message_content in expected_not_in_message_contents:
        assert expected_not_in_message_content not in message


def test_on_agent_relation_joined(
    harness: testing.Harness[JenkinsAgentCharm],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """arrange: given charm in its initial state
    act: when the slave_relation_joined occurs
    assert: then the agent sets the executors, labels and slave hosts relation data.
    """
    # Mock uname and CPU count
    mock_os_cpu_count = mock.MagicMock()
    cpu_count = 8
    mock_os_cpu_count.return_value = cpu_count
    monkeypatch.setattr(os, "cpu_count", mock_os_cpu_count)
    mock_os_uname = mock.MagicMock()
    machine_architecture = "x86_64"
    mock_os_uname.return_value.machine = machine_architecture
    monkeypatch.setattr(os, "uname", mock_os_uname)

    caplog.set_level(logging.INFO)
    harness.enable_hooks()
    relation_id = harness.add_relation("slave", "jenkins")
    unit_name = "jenkins-agent-k8s/0"
    harness.add_relation_unit(relation_id, unit_name)

    assert harness.get_relation_data(relation_id, unit_name) == {
        'executors': str(cpu_count),
        'labels': machine_architecture,
        'slavehost': unit_name.replace("/", "-"),
    }
    assert "relation" in caplog.text.lower()
    assert "joined" in caplog.text.lower()


# class TestJenkinsAgentCharm(unittest.TestCase):
#     def setUp(self):
#         self.harness = Harness(JenkinsAgentCharm)
#         self.addCleanup(self.harness.cleanup)
#         self.harness.begin()
#         self.harness.disable_hooks()
#         self.harness.update_config(CONFIG_DEFAULT)

#     @patch("charm.JenkinsAgentCharm._on_config_changed")
#     def test__valid_relation_data__no__jenkins_url(self, mock_on_config_changed):
#         """Test valid_relation_data when no configuration has been provided."""
#         with self.assertLogs(level='INFO') as logger:
#             self.harness.charm.valid_relation_data()
#             expected_output = [
#                 "INFO:root:Setting up jenkins via agent relation",
#                 "INFO:root:Jenkins hasn't exported its URL yet. Skipping setup for now.",
#             ]
#             self.assertEqual(logger.output, expected_output)
#             mock_on_config_changed.assert_not_called()
#             self.assertEqual(self.harness.model.unit.status, ActiveStatus())

#     @patch("charm.JenkinsAgentCharm._on_config_changed")
#     def test__valid_relation_data__no__jenkins_agent_tokens(self, mock_on_config_changed):
#         """Test valid_relation_data when no tokens have been provided."""
#         self.harness.charm._stored.jenkins_url = "http://test"
#         with self.assertLogs(level='INFO') as logger:
#             self.harness.charm.valid_relation_data()
#             expected_output = [
#                 "INFO:root:Setting up jenkins via agent relation",
#                 "INFO:root:Jenkins hasn't exported the agent secret yet. Skipping setup for now.",
#             ]
#             self.assertEqual(logger.output, expected_output)
#             mock_on_config_changed.assert_not_called()
#             self.assertEqual(self.harness.model.unit.status, ActiveStatus())

#     @patch("charm.JenkinsAgentCharm._on_config_changed")
#     def test__valid_relation_data__manual__config(self, mock_on_config_changed):
#         """Test valid_relation_data when no configuration has been provided."""
#         self.harness.update_config({"jenkins_url": "http://test"})
#         with self.assertLogs(level='INFO') as logger:
#             self.harness.charm.valid_relation_data()
#             expected_output = [
#                 "INFO:root:Setting up jenkins via agent relation",
#                 "INFO:root:Config option 'jenkins_url' is set. Can't use agent relation.",
#             ]
#             self.assertEqual(logger.output, expected_output)
#             mock_on_config_changed.assert_not_called()
#             self.assertEqual(self.harness.model.unit.status, ActiveStatus())

#     def test__valid_relation_data(self):
#         """Test valid_relation_data when the relation have provided all needed data."""
#         self.harness.charm._stored.jenkins_url = "http://test"
#         self.harness.charm._stored.agent_tokens = "token"
#         with self.assertLogs(level='INFO') as logger:
#             self.harness.charm.valid_relation_data()
#             expected_output = "INFO:root:Setting up jenkins via agent relation"
#             self.assertEqual(logger.output[-1], expected_output)
#             self.assertEqual(self.harness.model.unit.status, MaintenanceStatus("Configuring jenkins agent"))

#     @patch("charm.JenkinsAgentCharm._on_config_changed")
#     @patch("os.uname")
#     @patch("os.cpu_count")
#     def test__on_agent_relation_joined__custom__label(self, mock_os_cpu_count, mock_os_uname, mock_on_config_changed):
#         """Test relation_data is set when a new relation joins
#         and custom labels are set"""
#         mock_os_cpu_count.return_value = 8
#         mock_os_uname.return_value.machine = "x86_64"
#         labels = "test, label"
#         expected_relation_data = {'executors': '8', 'labels': labels, 'slavehost': 'alejdg-jenkins-agent-k8s-0'}
#         self.harness.update_config({"jenkins_agent_labels": labels})
#         self.harness.enable_hooks()
#         rel_id = self.harness.add_relation("slave", "jenkins")
#         self.harness.add_relation_unit(rel_id, "jenkins/0")
#         self.assertEqual(self.harness.get_relation_data(rel_id, "alejdg-jenkins-agent-k8s/0"), expected_relation_data)
#         mock_on_config_changed.assert_not_called()

#     @patch("charm.JenkinsAgentCharm._on_config_changed")
#     @patch("os.uname")
#     @patch("os.cpu_count")
#     def test__on_agent_relation_changed__noop(self, mock_os_cpu_count, mock_os_uname, mock_on_config_changed):
#         """Test on_agent_relation_changed when jenkins hasn't provided information yet."""
#         mock_os_cpu_count.return_value = 8
#         mock_os_uname.return_value.machine = "x86_64"
#         remote_unit = "jenkins/0"
#         self.harness.enable_hooks()
#         rel_id = self.harness.add_relation("slave", "jenkins")
#         self.harness.add_relation_unit(rel_id, remote_unit)
#         self.harness.update_relation_data(rel_id, remote_unit, {})

#         mock_on_config_changed.assert_not_called()

#     @patch("charm.JenkinsAgentCharm.valid_relation_data")
#     @patch("os.uname")
#     @patch("os.cpu_count")
#     def test__on_agent_relation_changed_old(self, mock_os_cpu_count, mock_os_uname, mock_valid_relation_data):
#         """Test relation_data is set when a new relation joins."""
#         mock_os_cpu_count.return_value = 8
#         mock_os_uname.return_value.machine = "x86_64"
#         remote_unit = "jenkins/0"
#         agent_name = "alejdg-jenkins-agent-k8s-0"
#         url = "http://test"
#         secret = "token"
#         self.harness.enable_hooks()
#         rel_id = self.harness.add_relation("slave", "jenkins")
#         self.harness.add_relation_unit(rel_id, remote_unit)
#         self.harness.update_relation_data(rel_id, remote_unit, {"url": url, "secret": secret})
#         self.assertEqual(self.harness.charm._stored.jenkins_url, url)
#         self.assertEqual(self.harness.charm._stored.agent_tokens[-1], secret)
#         self.assertEqual(self.harness.charm._stored.agents[-1], agent_name)
#         mock_valid_relation_data.assert_called()

#     @patch("charm.JenkinsAgentCharm._on_config_changed")
#     @patch("os.uname")
#     @patch("os.cpu_count")
#     def test__on_agent_relation_changed__multiple__agents(
#         self, mock_os_cpu_count, mock_os_uname, mock_on_config_changed
#     ):
#         """Test relation_data is set when a new relation joins."""
#         mock_os_cpu_count.return_value = 8
#         mock_os_uname.return_value.machine = "x86_64"
#         remote_unit = "jenkins/0"
#         agent_name = "alejdg-jenkins-agent-k8s-0"
#         expected_new_agent = "alejdg-jenkins-agent-k8s-1"
#         url = "http://test"
#         secret = "token"

#         self.harness.charm._stored.agents = [agent_name]
#         self.harness.enable_hooks()
#         rel_id = self.harness.add_relation("slave", "jenkins")
#         self.harness.add_relation_unit(rel_id, remote_unit)
#         self.harness.update_relation_data(rel_id, remote_unit, {"url": url, "secret": secret})
#         self.assertEqual(self.harness.charm._stored.jenkins_url, url)
#         self.assertEqual(self.harness.charm._stored.agent_tokens[-1], secret)
#         self.assertEqual(self.harness.charm._stored.agents[-1], expected_new_agent)
#         mock_on_config_changed.assert_called()
