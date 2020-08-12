# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import unittest

from ops import testing
from ops.model import ActiveStatus, BlockedStatus


import sys

sys.path.append('src')  # noqa: E402

from charm import JenkinsAgentCharm

CONFIG_DEFAULT = {
    "image": "jenkins-agent-operator",
    "jenkins_master_url": "",
    "jenkins_agent_name": "",
    "jenkins_agent_token": ""
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
        expected = {
            "JENKINS_URL": "http://test",
        }
        self.assertEqual(self.harness.charm.generate_pod_config(CONFIG_ONE_AGENT, secured=True), expected)

        expected["JENKINS_AGENTS"] = "agent-one"
        expected["JENKINS_TOKENS"] = "token-one"
        self.assertEqual(self.harness.charm.generate_pod_config(CONFIG_ONE_AGENT, secured=False), expected)

    def test__configure_pod__invalid__config(self):
        """Test configure_pod when the config is invalid"""
        self.harness.charm.on.config_changed.emit()
        message = "Missing required config: jenkins_master_url jenkins_agent_name jenkins_agent_token"
        self.assertEqual(self.harness.model.unit.status, BlockedStatus(message))
        self.assertEqual(self.harness.get_pod_spec(), None)

    def test__configure_pod__unit__not__leader(self):
        """Test configure_pod when the unit isn't leader"""
        self.harness.set_leader(is_leader=False)
        self.harness.update_config(CONFIG_ONE_AGENT)
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.on.config_changed.emit()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())
            message = "INFO:root:Spec changes ignored by non-leader"
            self.assertEqual(logger.output[-1], message)
            self.assertEqual(self.harness.get_pod_spec(), None)

    def test__configure_pod(self):
        """Test configure_pod"""
        expected = (SPEC_EXPECTED, None)

        self.harness.set_leader(is_leader=True)
        self.harness.update_config(CONFIG_ONE_AGENT_CUSTOM_IMAGE)
        with self.assertLogs(level='INFO') as logger:
            print(self.harness.get_pod_spec())
            self.harness.charm.on.config_changed.emit()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())
            self.assertEqual(self.harness.get_pod_spec(), expected)

    def test__configure_pod__no__spec_change(self):
        """Test configure_pod when there is no change in the spec"""
        self.harness.set_leader(is_leader=True)
        self.harness.update_config(CONFIG_ONE_AGENT_CUSTOM_IMAGE)
        self.harness.charm._stored._spec = self.harness.charm.make_pod_spec()
        with self.assertLogs(level='INFO') as logger:
            self.harness.charm.on.config_changed.emit()
            self.assertEqual(self.harness.model.unit.status, ActiveStatus())
            print(logger.output[-1])
            message = "INFO:root:Pod spec unchanged"
            self.assertEqual(logger.output[-1], message)
            self.assertEqual(self.harness.get_pod_spec(), None)

    def test__make_pod_spec(self):
        """Test the construction of the spec based on juju config"""
        self.harness.update_config(CONFIG_ONE_AGENT_CUSTOM_IMAGE)
        self.assertEqual(self.harness.charm.make_pod_spec(), SPEC_EXPECTED)

    def test__is_valid_config(self):
        """Test config validation"""
        config = {
            "image": "image-name",
            "jenkins_master_url": "http://test",
            "jenkins_agent_name": "agent-one",
            "jenkins_agent_token": "token-one"
        }
        self.assertEqual(self.harness.charm.is_valid_config(), False)
        self.harness.update_config(config)
        self.assertEqual(self.harness.charm.is_valid_config(), True)
