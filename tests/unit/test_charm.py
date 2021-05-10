# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

from mock import MagicMock, patch
import unittest

from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

from charm import JenkinsAgentCharm

SERVICE_NAME = "jenkins-agent"

CONFIG_DEFAULT = {
    "image": "jenkins-agent-operator",
    "jenkins_url": "",
    "jenkins_agent_name": "",
    "jenkins_agent_token": "",
    "jenkins_agent_label": ""
}

CONFIG_ONE_AGENT = {
    "jenkins_url": "http://test",
    "jenkins_agent_name": "agent-one",
    "jenkins_agent_token": "token-one"
}

CONFIG_ONE_AGENT_CUSTOM_IMAGE = {
    "image": "image-name",
    "jenkins_url": "http://test",
    "jenkins_agent_name": "agent-one",
    "jenkins_agent_token": "token-one"
}

ENV_INITIAL = {
    'JENKINS_AGENTS': '',
    'JENKINS_TOKENS': '',
    'JENKINS_URL': ''
}

ENV_ONE_AGENT = {
    'JENKINS_AGENTS': 'agent-one',
    'JENKINS_TOKENS': 'token-one',
    'JENKINS_URL': 'http://test'
}

SPEC_EXPECTED = {
    'containers': [{
        'config': {
            'JENKINS_AGENTS': 'agent-one',
            'JENKINS_TOKENS': 'token-one',
            'JENKINS_URL': 'http://test'
        },
        'imageDetails': {
            'imagePath': 'image-name'
        },
        'name': 'jenkins-agent',
        'readinessProbe': {
            'exec': {
                'command': [
                    '/bin/cat',
                    '/var/lib/jenkins/agents/.ready'
                ]
            }
        }
    }]
}


class TestJenkinsAgentCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(JenkinsAgentCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.harness.disable_hooks()
        self.harness.update_config(CONFIG_DEFAULT)

    def test__get_env_config(self):
        """Test _get_env_config with config data"""
        self.assertEqual(self.harness.charm._get_env_config(), ENV_INITIAL)
        self.harness.update_config(CONFIG_ONE_AGENT)
        self.assertEqual(self.harness.charm._get_env_config(), ENV_ONE_AGENT)

    def test__get_env_config__with__relation__data(self):
        """Test get_env_config with relation data."""
        self.harness.update_config(CONFIG_ONE_AGENT)
        self.harness.charm._stored.jenkins_url = CONFIG_ONE_AGENT["jenkins_url"]
        self.harness.charm._stored.agents = [CONFIG_ONE_AGENT["jenkins_agent_name"]]
        self.harness.charm._stored.agent_tokens = [CONFIG_ONE_AGENT["jenkins_agent_token"]]

        self.assertEqual(self.harness.charm._get_env_config(), ENV_ONE_AGENT)

    def test__invalid__config(self):
        """Test config changed when the config is invalid."""
        self.harness.charm.on.config_changed.emit()
        message = "Missing required config: jenkins_agent_name jenkins_agent_token jenkins_url"
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(message))
        self.assertEqual(self.harness.get_pod_spec(), None)

    def test__restart_service(self):
        """Test restarting a service"""
        mock_container = MagicMock()
        with self.subTest("Service not running"):
            mock_container.get_service.return_value.is_running.return_value = False
            self.harness.charm._restart_service(SERVICE_NAME, mock_container)
            mock_container.stop.assert_not_called()
            mock_container.start.assert_called()
        with self.subTest("Service already running"):
            mock_container.get_service.return_value.is_running.return_value = True
            self.harness.charm._restart_service(SERVICE_NAME, mock_container)
            mock_container.get_service.return_value.is_running.assert_called()
            mock_container.stop.assert_called()
            mock_container.start.assert_called()

    def test__config_changed(self):
        """Test config changed."""

        self.harness.update_config(CONFIG_ONE_AGENT)
        self.harness.charm.on.config_changed.emit()
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test__config_changed__no__spec_change(self):
        """Test config changed when there is no change in the spec."""
        mock_event = MagicMock()
        self.harness.update_config(CONFIG_ONE_AGENT)
        pebble_config = self.harness.charm._get_pebble_config(mock_event)
        container = self.harness.model.unit.get_container(SERVICE_NAME)
        container.add_layer(SERVICE_NAME, pebble_config, combine=True)
        with self.assertLogs(level='DEBUG') as logger:
            self.harness.charm.on.config_changed.emit()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())
            message = "DEBUG:root:Pebble config unchanged"
            self.assertEqual(logger.output[-1], message)

    def test__is_valid_config(self):
        """Test config validation."""
        config = {
            "image": "image-name",
            "jenkins_url": "http://test",
            "jenkins_agent_name": "agent-one",
            "jenkins_agent_token": "token-one"
        }
        self.assertEqual(self.harness.charm._is_valid_config(), False)
        with self.subTest("Config from relation"):
            self.harness.charm._stored.agent_tokens = "token"
            self.assertEqual(self.harness.charm._is_valid_config(), True)
        with self.subTest("Config from juju config"):
            self.harness.update_config(config)
            self.assertEqual(self.harness.charm._is_valid_config(), True)

    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_joined(self, mock_os_cpu_count, mock_os_uname):
        """Test relation_data is set when a new relation joins."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        expected_relation_data = {
            'executors': '8',
            'labels': 'x86_64',
            'slavehost': 'alejdg-jenkins-agent-k8s-0'
        }
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, "alejdg-jenkins-agent-k8s/0")

        self.assertEqual(self.harness.get_relation_data(rel_id, "alejdg-jenkins-agent-k8s/0"), expected_relation_data)

    @patch("charm.JenkinsAgentCharm._on_config_changed")
    def test__valid_relation_data__no__jenkins_url(self, mock_on_config_changed):
        """Test valid_relation_data when no configuration has been provided."""
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.valid_relation_data()
            expected_output = [
                "INFO:root:Setting up jenkins via agent relation",
                "INFO:root:Jenkins hasn't exported its URL yet. Skipping setup for now."
            ]
            self.assertEqual(logger.output, expected_output)
            mock_on_config_changed.assert_not_called()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    @patch("charm.JenkinsAgentCharm._on_config_changed")
    def test__valid_relation_data__no__jenkins_agent_tokens(self, mock_on_config_changed):
        """Test valid_relation_data when no tokens have been provided."""
        self.harness.charm._stored.jenkins_url = "http://test"
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.valid_relation_data()
            expected_output = [
                "INFO:root:Setting up jenkins via agent relation",
                "INFO:root:Jenkins hasn't exported the agent secret yet. Skipping setup for now."
            ]
            self.assertEqual(logger.output, expected_output)
            mock_on_config_changed.assert_not_called()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    @patch("charm.JenkinsAgentCharm._on_config_changed")
    def test__valid_relation_data__manual__config(self, mock_on_config_changed):
        """Test valid_relation_data when no configuration has been provided."""
        self.harness.update_config({"jenkins_url": "http://test"})
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.valid_relation_data()
            expected_output = [
                "INFO:root:Setting up jenkins via agent relation",
                "INFO:root:Config option 'jenkins_url' is set. Can't use agent relation."
            ]
            self.assertEqual(logger.output, expected_output)
            mock_on_config_changed.assert_not_called()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    def test__valid_relation_data(self):
        """Test valid_relation_data when the relation have provided all needed data."""
        self.harness.charm._stored.jenkins_url = "http://test"
        self.harness.charm._stored.agent_tokens = "token"
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.valid_relation_data()
            expected_output = "INFO:root:Setting up jenkins via agent relation"
            self.assertEqual(logger.output[-1], expected_output)
            self.assertEqual(self.harness.model.unit.status, MaintenanceStatus("Configuring jenkins agent"))

    @patch("charm.JenkinsAgentCharm._on_config_changed")
    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_joined__custom__label(self, mock_os_cpu_count, mock_os_uname, mock_on_config_changed):
        """Test relation_data is set when a new relation joins
            and custom labels are set"""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        labels = "test, label"
        expected_relation_data = {
            'executors': '8',
            'labels': labels,
            'slavehost': 'alejdg-jenkins-agent-k8s-0'
        }
        self.harness.update_config({"jenkins_agent_labels": labels})
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, "jenkins/0")
        self.assertEqual(self.harness.get_relation_data(rel_id, "alejdg-jenkins-agent-k8s/0"), expected_relation_data)
        mock_on_config_changed.assert_not_called()

    @patch("charm.JenkinsAgentCharm._on_config_changed")
    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_changed__noop(self, mock_os_cpu_count, mock_os_uname, mock_on_config_changed):
        """Test on_agent_relation_changed when jenkins hasn't provided information yet."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        remote_unit = "jenkins/0"
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, remote_unit)
        self.harness.update_relation_data(rel_id, remote_unit, {})

        mock_on_config_changed.assert_not_called()

    @patch("charm.JenkinsAgentCharm.valid_relation_data")
    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_changed_old(self, mock_os_cpu_count, mock_os_uname, mock_valid_relation_data):
        """Test relation_data is set when a new relation joins."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        remote_unit = "jenkins/0"
        agent_name = "alejdg-jenkins-agent-k8s-0"
        url = "http://test"
        secret = "token"
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, remote_unit)
        self.harness.update_relation_data(rel_id, remote_unit, {"url": url, "secret": secret})
        self.assertEqual(self.harness.charm._stored.jenkins_url, url)
        self.assertEqual(self.harness.charm._stored.agent_tokens[-1], secret)
        self.assertEqual(self.harness.charm._stored.agents[-1], agent_name)
        mock_valid_relation_data.assert_called()

    @patch("charm.JenkinsAgentCharm._on_config_changed")
    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_changed__multiple__agents(
        self,
        mock_os_cpu_count,
        mock_os_uname,
        mock_on_config_changed
    ):
        """Test relation_data is set when a new relation joins."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        remote_unit = "jenkins/0"
        agent_name = "alejdg-jenkins-agent-k8s-0"
        expected_new_agent = "alejdg-jenkins-agent-k8s-1"
        url = "http://test"
        secret = "token"

        self.harness.charm._stored.agents = [agent_name]
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, remote_unit)
        self.harness.update_relation_data(rel_id, remote_unit, {"url": url, "secret": secret})
        self.assertEqual(self.harness.charm._stored.jenkins_url, url)
        self.assertEqual(self.harness.charm._stored.agent_tokens[-1], secret)
        self.assertEqual(self.harness.charm._stored.agents[-1], expected_new_agent)
        mock_on_config_changed.assert_called()
