# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-k8s-agent server module tests."""


import secrets
import typing
import unittest.mock

import ops
import ops.testing
import pytest
import requests

import server
import state
from charm import JenkinsAgentCharm


def test_credentials_from_jenkins_slave_interface_dict_partial(harness: ops.testing.Harness):
    """
    arrange: given a slave relation databag containing partial url data.
    act: when from_jenkins_slave_interface_dict is called.
    assert: None is returned.
    """
    relation_id = harness.add_relation(state.SLAVE_RELATION, "jenkins")
    harness.add_relation_unit(relation_id=relation_id, remote_unit_name="jenkins/0")
    harness.update_relation_data(
        relation_id=relation_id, app_or_unit="jenkins/0", key_values={"url": "http://test-url"}
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    relation = jenkins_charm.model.get_relation(state.SLAVE_RELATION, relation_id=relation_id)
    jenkins_unit = jenkins_charm.model.get_unit("jenkins/0")
    relation_data = relation.data.get(jenkins_unit)
    assert relation_data, "relation data with jenkins unit should not be None."
    assert not server.Credentials.from_jenkins_slave_interface_dict(
        server_unit_databag=relation_data
    )


def test_credentials_from_jenkins_slave_interface_dict(harness: ops.testing.Harness):
    """
    arrange: given a slave relation databag containing partial url data.
    act: when from_jenkins_slave_interface_dict is called.
    assert: None is returned.
    """
    test_url = "http://test-url"
    test_secret = secrets.token_hex(16)
    relation_id = harness.add_relation(state.SLAVE_RELATION, "jenkins")
    harness.add_relation_unit(relation_id=relation_id, remote_unit_name="jenkins/0")
    harness.update_relation_data(
        relation_id=relation_id,
        app_or_unit="jenkins/0",
        key_values={"url": test_url, "secret": test_secret},
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    relation = jenkins_charm.model.get_relation(state.SLAVE_RELATION, relation_id=relation_id)
    jenkins_unit = jenkins_charm.model.get_unit("jenkins/0")
    relation_data = relation.data.get(jenkins_unit)
    assert relation_data, "relation data with jenkins unit should not be None."
    assert server.Credentials.from_jenkins_slave_interface_dict(
        server_unit_databag=relation_data
    ) == server.Credentials(address=test_url, secret=test_secret)


def test_credentials_from_jenkins_agent_interface_dict_partial(harness: ops.testing.Harness):
    """
    arrange: given a agent relation databag containing partial url data.
    act: when from_jenkins_agent_v0_interface_dict is called.
    assert: None is returned.
    """
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id=relation_id, remote_unit_name="jenkins/0")
    harness.update_relation_data(
        relation_id=relation_id, app_or_unit="jenkins/0", key_values={"url": "http://test-url"}
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    relation = jenkins_charm.model.get_relation(state.AGENT_RELATION, relation_id=relation_id)
    jenkins_unit = jenkins_charm.model.get_unit("jenkins/0")
    relation_data = relation.data.get(jenkins_unit)
    assert relation_data, "relation data with jenkins unit should not be None."
    assert not server.Credentials.from_jenkins_agent_v0_interface_dict(
        server_unit_databag=relation_data, unit_name=jenkins_charm.unit.name
    )


def test_credentials_from_jenkins_agent_interface_dict(harness: ops.testing.Harness):
    """
    arrange: given a agent relation databag containing partial url data.
    act: when from_jenkins_agent_v0_interface_dict is called.
    assert: None is returned.
    """
    test_url = "http://test-url"
    test_secret = secrets.token_hex(16)
    relation_id = harness.add_relation(state.AGENT_RELATION, "jenkins")
    harness.add_relation_unit(relation_id=relation_id, remote_unit_name="jenkins/0")
    harness.update_relation_data(
        relation_id=relation_id,
        app_or_unit="jenkins/0",
        key_values={"url": test_url, f"{harness.model.unit.name}_secret": test_secret},
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    relation = jenkins_charm.model.get_relation(state.AGENT_RELATION, relation_id=relation_id)
    jenkins_unit = jenkins_charm.model.get_unit("jenkins/0")
    relation_data = relation.data.get(jenkins_unit)
    assert relation_data, "relation data with jenkins unit should not be None."
    assert server.Credentials.from_jenkins_agent_v0_interface_dict(
        server_unit_databag=relation_data, unit_name=harness.model.unit.name
    ) == server.Credentials(address=test_url, secret=test_secret)


def test_get_credentials_no_databag():
    """
    arrange: given no databag.
    act: when get_credentials is called.
    assert: None is returned.
    """
    assert not server.get_credentials(
        relation_name="test-relation", unit_name="test-agent", databag=None
    )


@pytest.mark.parametrize(
    "relation",
    [
        pytest.param(state.SLAVE_RELATION, id="Slave relation"),
        pytest.param(state.AGENT_RELATION, id="Agent relation"),
    ],
)
def test_get_credentials_relation(relation: str):
    """
    arrange: given a mocked relation databag.
    act: when get_credentials is called
    assert: Credentials with databag content is returned.
    """
    test_content = "some_content"
    mock_databag = unittest.mock.MagicMock(spec=ops.RelationDataContent)
    mock_databag.get = lambda *_args, **_kwargs: test_content
    assert server.get_credentials(
        relation_name=relation, unit_name="test-agent", databag=mock_databag
    ) == server.Credentials(address=test_content, secret=test_content)


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
        server.download_jenkins_agent(
            server_url="http://test-url", connectable_container=mock_contaier
        )


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
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)
    server.download_jenkins_agent(
        server_url="http://test-url", connectable_container=jenkins_charm._jenkins_agent_container
    )

    assert (
        str(
            jenkins_charm._jenkins_agent_container.pull(
                server.AGENT_JAR_PATH, encoding="utf-8"
            ).read()
        )
        == response_content
    )


def test_validate_credentials_fail():
    """
    arrange: given a mock container that returns unsuccessful jenkins slave connection logs.
    act: when validate_credentials is called.
    assert: False is returned.
    """
    mock_process = unittest.mock.MagicMock(spec=ops.pebble.ExecProcess)
    mock_process.stdout = ("a", "b", "c")
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.exec.return_value = mock_process

    assert not server.validate_credentials(
        agent_name="test-agent",
        credentials=server.Credentials(address="http://test-url", secret=secrets.token_hex(16)),
        connectable_container=mock_container,
    )


def test_validate_credentials_terminated():
    """
    arrange: given a mock container that returns unsuccessful jenkins slave connection logs.
    act: when validate_credentials is called.
    assert: False is returned.
    """
    mock_process = unittest.mock.MagicMock(spec=ops.pebble.ExecProcess)
    mock_process.stdout = ("a", "b", "INFO: Terminated")
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.exec.return_value = mock_process

    assert not server.validate_credentials(
        agent_name="test-agent",
        credentials=server.Credentials(address="http://test-url", secret=secrets.token_hex(16)),
        connectable_container=mock_container,
    )


def test_validate_credentials():
    """
    arrange: given a mock container that returns unsuccessful jenkins slave connection logs.
    act: when validate_credentials is called.
    assert: True is returned.
    """
    mock_process = unittest.mock.MagicMock(spec=ops.pebble.ExecProcess)
    mock_process.stdout = ("INFO: Connected",)
    mock_container = unittest.mock.MagicMock(spec=ops.Container)
    mock_container.exec.return_value = mock_process

    assert server.validate_credentials(
        agent_name="test-agent",
        credentials=server.Credentials(address="http://test-url", secret=secrets.token_hex(16)),
        connectable_container=mock_container,
    )


def test_is_registered_no_pebble_servce(harness: ops.testing.Harness):
    """
    arrange: given a container with no pebble workload that has set AGENT_READY_PATH.
    act: when is_registered is called.
    assert: False is returned.
    """
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)

    assert not server.is_registered(connectable_container=jenkins_charm._jenkins_agent_container)


def test_is_registered(harness: ops.testing.Harness):
    """
    arrange: given a container with AGENT_READY_PATH set by pebble workload.
    act: when is_registered is called.
    assert: True is returned.
    """
    harness.set_can_connect("jenkins-k8s-agent", True)
    harness.model.unit.get_container("jenkins-k8s-agent").push(
        server.AGENT_READY_PATH, "content", encoding="utf-8", make_dirs=True
    )
    harness.begin()

    jenkins_charm = typing.cast(JenkinsAgentCharm, harness.charm)

    assert server.is_registered(connectable_container=jenkins_charm._jenkins_agent_container)
