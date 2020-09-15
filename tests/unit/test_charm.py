# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

from mock import MagicMock, patch
import unittest

from ops import testing
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

from charm import JenkinsAgentCharm

CONFIG_DEFAULT = {
    "image": "jenkins-agent-operator",
    "jenkins_master_url": "",
    "jenkins_agent_name": "",
    "jenkins_agent_token": "",
    "jenkins_agent_label": ""
}

CONFIG_ONE_AGENT = {
    "jenkins_master_url": "http://test",
    "jenkins_agent_name": "agent-one",
    "jenkins_agent_token": "token-one"
}

CONFIG_ONE_AGENT_CUSTOM_IMAGE = {
    "image": "image-name",
    "jenkins_master_url": "http://test",
    "jenkins_agent_name": "agent-one",
    "jenkins_agent_token": "token-one"
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
        self.harness = testing.Harness(JenkinsAgentCharm)
        self.harness.begin()
        self.harness.disable_hooks()
        self.harness.update_config(CONFIG_DEFAULT)

    def test__generate_pod_config(self):
        """Test generate_pod_config"""
        expected = {
            "JENKINS_URL": "http://test",
        }
        self.assertEqual(self.harness.charm.generate_pod_config(CONFIG_ONE_AGENT, secured=True), expected)

        expected["JENKINS_AGENTS"] = "agent-one"
        expected["JENKINS_TOKENS"] = "token-one"
        self.assertEqual(self.harness.charm.generate_pod_config(CONFIG_ONE_AGENT, secured=False), expected)

    def test__generate_pod_config__with__relation__data(self):
        """Test generate_pod_config with relation data."""
        expected = {
            "JENKINS_URL": "http://test",
        }
        agent_name = "jenkins-agent-0"
        url = "http://test"
        token = "token"

        self.harness.charm._stored.jenkins_url = url
        self.harness.charm._stored.agent_tokens = [token]
        self.harness.charm._stored.agents = [agent_name]

        self.assertEqual(self.harness.charm.generate_pod_config(CONFIG_ONE_AGENT, secured=True), expected)

        expected["JENKINS_AGENTS"] = "jenkins-agent-0"
        expected["JENKINS_TOKENS"] = "token"
        self.assertEqual(self.harness.charm.generate_pod_config(CONFIG_ONE_AGENT, secured=False), expected)

    def test__configure_pod__invalid__config(self):
        """Test configure_pod when the config is invalid."""
        self.harness.charm.on.config_changed.emit()
        message = "Missing required config: jenkins_agent_name jenkins_agent_token jenkins_master_url"
        print(self.harness.model.unit.status)
        print(BlockedStatus(message))
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(message))
        self.assertEqual(self.harness.get_pod_spec(), None)

    def test__configure_pod__unit__not__leader(self):
        """Test configure_pod when the unit isn't leader."""
        self.harness.set_leader(is_leader=False)
        self.harness.update_config(CONFIG_ONE_AGENT)
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.on.config_changed.emit()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())
            message = "INFO:root:Spec changes ignored by non-leader"
            self.assertEqual(logger.output[-1], message)
            self.assertEqual(self.harness.get_pod_spec(), None)

    def test__configure_pod(self):
        """Test configure_pod."""
        expected = (SPEC_EXPECTED, None)

        self.harness.set_leader(is_leader=True)
        self.harness.update_config(CONFIG_ONE_AGENT_CUSTOM_IMAGE)
        self.harness.charm.on.config_changed.emit()
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        self.assertEqual(self.harness.get_pod_spec(), expected)

    def test__configure_pod__no__spec_change(self):
        """Test configure_pod when there is no change in the spec."""
        self.harness.set_leader(is_leader=True)
        self.harness.update_config(CONFIG_ONE_AGENT_CUSTOM_IMAGE)
        self.harness.charm._stored._spec = self.harness.charm.make_pod_spec()
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.on.config_changed.emit()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())
            message = "INFO:root:Pod spec unchanged"
            self.assertEqual(logger.output[-1], message)
            self.assertEqual(self.harness.get_pod_spec(), None)

    def test__make_pod_spec(self):
        """Test the construction of the spec based on juju config."""
        self.harness.update_config(CONFIG_ONE_AGENT_CUSTOM_IMAGE)
        self.assertEqual(self.harness.charm.make_pod_spec(), SPEC_EXPECTED)

    def test__is_valid_config(self):
        """Test config validation."""
        config = {
            "image": "image-name",
            "jenkins_master_url": "http://test",
            "jenkins_agent_name": "agent-one",
            "jenkins_agent_token": "token-one"
        }
        self.assertEqual(self.harness.charm.is_valid_config(), False)
        with self.subTest("Config from relation"):
            self.harness.charm._stored.agent_tokens = "token"
            self.assertEqual(self.harness.charm.is_valid_config(), True)
        with self.subTest("Config from juju config"):
            self.harness.update_config(config)
            self.assertEqual(self.harness.charm.is_valid_config(), True)

    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_joined(self, mock_os_cpu_count, mock_os_uname):
        """Test relation_data is set when a new relation joins."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        expected_relation_data = {
            'executors': '8',
            'labels': 'x86_64',
            'slavehost': 'jenkins-agent-0'
        }
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, "jenkins/0")

        self.assertEqual(self.harness.get_relation_data(rel_id, "jenkins-agent/0"), expected_relation_data)

    @patch("charm.JenkinsAgentCharm.configure_pod")
    def test__configure_through_relation__no__jenkins_master_url(self, mock_configure_pod):
        """Test configure_through_relation when no configuration has been provided."""
        mock_event = MagicMock()
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.configure_through_relation(mock_event)
            expected_output = [
                "INFO:root:Setting up jenkins via agent relation",
                "INFO:root:Jenkins hasn't exported its URL yet. Skipping setup for now."
            ]
            self.assertEqual(logger.output, expected_output)
            mock_configure_pod.assert_not_called()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    @patch("charm.JenkinsAgentCharm.configure_pod")
    def test__configure_through_relation__no__jenkins_agent_tokens(self, mock_configure_pod):
        """Test configure_through_relation when no tokens have been provided."""
        mock_event = MagicMock()
        self.harness.charm._stored.jenkins_url = "http://test"
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.configure_through_relation(mock_event)
            expected_output = [
                "INFO:root:Setting up jenkins via agent relation",
                "INFO:root:Jenkins hasn't exported the agent secret yet. Skipping setup for now."
            ]
            self.assertEqual(logger.output, expected_output)
            mock_configure_pod.assert_not_called()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    @patch("charm.JenkinsAgentCharm.configure_pod")
    def test__configure_through_relation__manual__config(self, mock_configure_pod):
        """Test configure_through_relation when no configuration has been provided."""
        mock_event = MagicMock()
        self.harness.update_config({"jenkins_master_url": "http://test"})
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.configure_through_relation(mock_event)
            expected_output = [
                "INFO:root:Setting up jenkins via agent relation",
                "INFO:root:Config option 'jenkins_master_url' is set. Can't use agent relation."
            ]
            self.assertEqual(logger.output, expected_output)
            mock_configure_pod.assert_not_called()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())

    @patch("charm.JenkinsAgentCharm.configure_pod")
    def test__configure_through_relation(self, mock_configure_pod):
        """Test configure_through_relation when the relation have provided all needed data."""
        mock_event = MagicMock()
        self.harness.charm._stored.jenkins_url = "http://test"
        self.harness.charm._stored.agent_tokens = "token"
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.configure_through_relation(mock_event)
            expected_output = [
                "INFO:root:Setting up jenkins via agent relation"
            ]
            self.assertEqual(logger.output, expected_output)
            mock_configure_pod.assert_called()
            self.assertEqual(self.harness.model.unit.status, MaintenanceStatus("Configuring jenkins agent"))

    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_joined__custom__label(self, mock_os_cpu_count, mock_os_uname):
        """Test relation_data is set when a new relation joins
            and custom labels are set"""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        labels = "test, label"
        expected_relation_data = {
            'executors': '8',
            'labels': labels,
            'slavehost': 'jenkins-agent-0'
        }
        self.harness.update_config({"jenkins_agent_labels": labels})
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, "jenkins/0")
        self.assertEqual(self.harness.get_relation_data(rel_id, "jenkins-agent/0"), expected_relation_data)

    @patch("charm.JenkinsAgentCharm.configure_through_relation")
    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_changed__noop(self, mock_os_cpu_count, mock_os_uname, mock_configure_through_relation):
        """Test on_agent_relation_changed when jenkins hasn't provided information yet."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        remote_unit = "jenkins/0"
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, remote_unit)
        self.harness.update_relation_data(rel_id, remote_unit, {})

        mock_configure_through_relation.assert_called()

    @patch("charm.JenkinsAgentCharm.configure_through_relation")
    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_changed_old(self, mock_os_cpu_count, mock_os_uname, mock_configure_through_relation):
        """Test relation_data is set when a new relation joins."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        remote_unit = "jenkins/0"
        agent_name = "jenkins-agent-0"
        url = "http://test"
        secret = "token"
        self.harness.enable_hooks()
        rel_id = self.harness.add_relation("slave", "jenkins")
        self.harness.add_relation_unit(rel_id, remote_unit)
        self.harness.update_relation_data(rel_id, remote_unit, {"url": url, "secret": secret})
        self.assertEqual(self.harness.charm._stored.jenkins_url, url)
        self.assertEqual(self.harness.charm._stored.agent_tokens[-1], secret)
        self.assertEqual(self.harness.charm._stored.agents[-1], agent_name)
        mock_configure_through_relation.assert_called()

    @patch("charm.JenkinsAgentCharm.configure_through_relation")
    @patch("os.uname")
    @patch("os.cpu_count")
    def test__on_agent_relation_changed__multiple__agents(
        self,
        mock_os_cpu_count,
        mock_os_uname,
        mock_configure_through_relation
    ):
        """Test relation_data is set when a new relation joins."""
        mock_os_cpu_count.return_value = 8
        mock_os_uname.return_value.machine = "x86_64"
        remote_unit = "jenkins/0"
        agent_name = "jenkins-agent-0"
        expected_new_agent = "jenkins-agent-1"
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
        mock_configure_through_relation.assert_called()
