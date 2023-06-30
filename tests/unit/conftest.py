# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Jenkins-k8s-operator charm unit tests."""

import secrets
import unittest.mock

import ops
import pytest
from ops.testing import Harness

import server
import state
from charm import JenkinsAgentCharm


@pytest.fixture(scope="function", name="harness")
def harness_fixture():
    """Enable ops test framework harness."""
    harness = Harness(JenkinsAgentCharm)

    yield harness

    harness.cleanup()


@pytest.fixture(scope="function", name="config")
def config_fixture():
    """The Jenkins testing configuration values."""
    return {
        "jenkins_url": "http://testingurl",
        "jenkins_agent_name": "testing_agent_name",
        "jenkins_agent_token": secrets.token_hex(16),
    }


@pytest.fixture(scope="function", name="mock_agent_relation_changed_event")
def mock_agent_relation_changed_event_fixture():
    """Relation changed event with name, data and unit data."""
    mock_relation_data = unittest.mock.MagicMock(spec=ops.RelationData)
    mock_relation = unittest.mock.MagicMock(spec=ops.Relation)
    mock_relation.name = state.AGENT_RELATION
    mock_relation.data = mock_relation_data
    mock_event = unittest.mock.MagicMock(spec=ops.RelationChangedEvent)
    mock_event.relation = mock_relation
    mock_event.unit = "jenkins/0"
    return mock_event


@pytest.fixture(scope="function", name="agent_credentials")
def agent_credentials_fixture():
    """Credentials from the Jenkins server charm."""
    return server.Credentials(address="http://test-jenkins-url", secret=secrets.token_hex(16))


@pytest.fixture(scope="function", name="raise_exception")
def raise_exception_fixture():
    """The mock function for patching."""

    def raise_exception(exception: Exception):
        """Raise exception function for monkeypatching.

        Args:
            exception: The exception to raise.

        Raises:
            exception: .
        """
        raise exception

    return raise_exception
