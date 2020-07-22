import unittest

import sys

sys.path.append('src')  # noqa: E402

from charm import generate_pod_config


class TestJenkinsAgentCharm(unittest.TestCase):
    def test_generate_pod_config(self):
        config = {
            "jenkins_user": "test",
        }
        expected = {
            "JENKINS_API_USER": "test",
        }
        self.assertEqual(generate_pod_config(config), expected)
