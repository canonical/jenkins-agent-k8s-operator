# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Jenkins-k8s-operator charm unit tests."""

import secrets
import typing
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
        "jenkins_url": "http://testingurl.com",
        "jenkins_agent_name": "testing_agent_name",
        "jenkins_agent_token": secrets.token_hex(16),
    }


@pytest.fixture(scope="function", name="get_mock_relation_changed_event")
def get_mock_relation_changed_event_fixture():
    """Relation changed event with name, data and unit data."""

    def get_mock_relation_changed_event(relation: str):
        """Create a new mock relation changed event.

        Args:
            relation: The target relation name.

        Returns:
            The mock relation event with Jenkins server.
        """
        mock_relation_data = unittest.mock.MagicMock(spec=ops.RelationData)
        mock_relation = unittest.mock.MagicMock(spec=ops.Relation)
        mock_relation.name = relation
        mock_relation.data = mock_relation_data
        mock_event = unittest.mock.MagicMock(spec=ops.RelationChangedEvent)
        mock_event.relation = mock_relation
        mock_event.unit = "jenkins/0"
        return mock_event

    return get_mock_relation_changed_event


@pytest.fixture(scope="function", name="get_valid_relation_data")
def get_valid_relation_data_fixture():
    """Relation changed event with name, data and unit data."""

    def get_valid_relation_data(relation: str):
        """Create a new mock relation changed event.

        Args:
            relation: The target relation name.

        Returns:
            The relation data for given relation.
        """
        if relation == state.AGENT_RELATION:
            return {"url": "test_url", "jenkins-agent-k8s-0_secret": secrets.token_hex(16)}
        return {"url": "test_url", "secret": secrets.token_hex(16)}

    return get_valid_relation_data


@pytest.fixture(scope="function", name="get_event_relation_data")
def get_event_relation_data_fixture(
    get_mock_relation_changed_event: typing.Callable[[str], unittest.mock.MagicMock],
    get_valid_relation_data: typing.Callable[[str], typing.Dict[str, str]],
):
    """A wrapper to reduce fixgure arguments to get mock event and relation data."""

    def wrap_event_relation_data(relation: str):
        """Wrap mock event and relation data.

        Args:
            relation: The target relation name.

        Returns:
            A tuple wrapping mock relation changed event and relation data.
        """
        return (
            get_mock_relation_changed_event(relation),
            get_valid_relation_data(relation),
        )

    return wrap_event_relation_data


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


@pytest.fixture(scope="function", name="jenkins_error_log")
def jenkins_error_log_fixture():
    """The logs produced by Jenkins agent on failed connection."""
    return """<TIME_REDACTED> org.jenkinsci.remoting.engine.WorkDirManager initializeWorkDir
INFO: Using /var/lib/jenkins/remoting as a remoting work directory
<TIME_REDACTED> org.jenkinsci.remoting.engine.WorkDirManager setupLogging
INFO: Both error and output logs will be printed to /var/lib/jenkins/remoting
[Fatal Error] :1:1: Invalid byte 1 of 1-byte UTF-8 sequence.
Exception in thread "main" org.xml.sax.SAXParseException; lineNumber: 1; columnNumber: 1; Invalid byte 1 of 1-byte UTF-8 sequence.
    """


@pytest.fixture(scope="function", name="jenkins_used_credential_log")
def jenkins_used_credential_log_fixture():
    """The logs produced by Jenkins agent on using an already registered credential."""
    return "Given agent already registered. Skipping."


@pytest.fixture(scope="function", name="jenkins_connection_log")
def jenkins_connection_log_fixture():
    """The logs produced by Jenkins on successful connection."""
    return """<TIME_REDACTED> hudson.remoting.jnlp.Main createEngine
INFO: Setting up agent: jenkins-agent-k8s-0
<TIME_REDACTED> hudson.remoting.Engine startEngine
INFO: Using Remoting version: 3107.v665000b_51092
<TIME_REDACTED> org.jenkinsci.remoting.engine.WorkDirManager initializeWorkDir
INFO: Using /var/lib/jenkins/remoting as a remoting work directory
<TIME_REDACTED> hudson.remoting.jnlp.Main$CuiListener status
INFO: Locating server among [<IP_REDACTED>]
<TIME_REDACTED> org.jenkinsci.remoting.engine.JnlpAgentEndpointResolver resolve
INFO: Remoting server accepts the following protocols: [JNLP4-connect, Ping]
<TIME_REDACTED> hudson.remoting.jnlp.Main$CuiListener status
INFO: Agent discovery successful
  Agent address: <IP_REDACTED>
  Agent port:    <PORT_REDACTED>
  Identity:      <IP_REDACTED>
<TIME_REDACTED> hudson.remoting.jnlp.Main$CuiListener status
INFO: Handshaking
<TIME_REDACTED> hudson.remoting.jnlp.Main$CuiListener status
INFO: Connecting to <IP_REDACTED>:<PORT_REDACTED>
<TIME_REDACTED> hudson.remoting.jnlp.Main$CuiListener status
INFO: Trying protocol: JNLP4-connect
<TIME_REDACTED> org.jenkinsci.remoting.protocol.impl.BIONetworkLayer$Reader run
INFO: Waiting for ProtocolStack to start.
<TIME_REDACTED> hudson.remoting.jnlp.Main$CuiListener status
INFO: Remote identity confirmed: <IP_REDACTED>
<TIME_REDACTED> hudson.remoting.jnlp.Main$CuiListener status
INFO: Connected
"""


@pytest.fixture(scope="function", name="jenkins_terminated_connection_log")
def jenkins_terminated_connection_log_fixture(jenkins_connection_log: str):
    """The logs produced by Jenkins on terminated connection."""
    return jenkins_connection_log + "INFO: Terminated"
