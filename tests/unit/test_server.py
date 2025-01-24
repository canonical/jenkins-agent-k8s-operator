# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-agent-k8s server module tests."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import secrets
import typing
import unittest.mock

import ops
import ops.testing
import pytest
import requests

import server


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(requests.HTTPError, id="HTTPError"),
        pytest.param(requests.Timeout, id="TimeoutError"),
        pytest.param(requests.ConnectionError, id="ConnectionError"),
    ],
)
def test_download_jenkins_agent_download_error(
    monkeypatch: pytest.MonkeyPatch, raise_exception: typing.Callable, exception: Exception
):
    """
    arrange: given a monkeypatched requests.get that raises an exception.
    act: when download_jenkins_agent is called.
    assert: AgentJarDownloadError is raised.
    """
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: raise_exception(exception))
    mock_contaier = unittest.mock.MagicMock(spec=ops.Container)
    with pytest.raises(server.AgentJarDownloadError):
        server.download_jenkins_agent(server_url="http://test-url", container=mock_contaier)


def test_download_jenkins_agent_download(
    monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness
):
    """
    arrange: given a monkeypatched requests.get that returns the agent.jar content.
    act: when download_jenkins_agent is called.
    assert: the agent.jar is installed in the workload container.
    """
    response_content = "hello"
    mock_response = unittest.mock.MagicMock(spec=requests.Response)
    mock_response.content = response_content
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwags: mock_response)
    harness.set_can_connect("jenkins-agent-k8s", True)
    harness.begin()

    container = harness.model.unit.get_container("jenkins-agent-k8s")
    server.download_jenkins_agent(server_url="http://test-url", container=container)

    assert str(container.pull(server.AGENT_JAR_PATH, encoding="utf-8").read()) == response_content


@pytest.mark.parametrize(
    "failed_log_fixture",
    [
        pytest.param("jenkins_error_log", id="error log"),
        pytest.param("jenkins_used_credential_log", id="used credential log"),
        pytest.param("jenkins_terminated_connection_log", id="terminated connection log"),
    ],
)
def test_validate_credentials_fail(failed_log_fixture: str, request: pytest.FixtureRequest):
    """
    arrange: given a mock container that returns unsuccessful jenkins agent connection logs.
    act: when validate_credentials is called.
    assert: False is returned.
    """
    mock_process = unittest.mock.MagicMock(spec=ops.pebble.ExecProcess)
    mock_process.stdout = request.getfixturevalue(failed_log_fixture).split("\n")
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.exec.return_value = mock_process

    assert not server.validate_credentials(
        agent_name="test-agent",
        credentials=server.Credentials(address="http://test-url", secret=secrets.token_hex(16)),
        container=mock_container,
    )


@pytest.mark.parametrize(
    "random_delay",
    [
        pytest.param(True, id="Add delay"),
        pytest.param(False, id="No delay"),
    ],
)
def test_validate_credentials(jenkins_connection_log: str, random_delay: bool):
    """
    arrange: given a mock container that returns unsuccessful jenkins agent connection logs.
    act: when validate_credentials is called.
    assert: True is returned.
    """
    mock_process = unittest.mock.MagicMock(spec=ops.pebble.ExecProcess)
    mock_process.stdout = jenkins_connection_log.split("\n")
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.exec.return_value = mock_process

    assert server.validate_credentials(
        agent_name="test-agent",
        credentials=server.Credentials(address="http://test-url", secret=secrets.token_hex(16)),
        container=mock_container,
        add_random_delay=random_delay,
    )
