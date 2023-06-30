# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-k8s-agent state module tests."""

import os
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


def test_from_charm_invalid_agent_data(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given an invalid os cpu_count data.
    act: when the state is intialized from_charm.
    assert: InvalidStateError is raised.
    """
    monkeypatch.setattr(os, "cpu_count", lambda: 0)
    mock_charmbase = unittest.mock.MagicMock(spec=ops.CharmBase)
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm=mock_charmbase)


def test_from_charm_invalid_charm_config(harness: ops.testing.Harness):
    """
    arrange: given an invalid charm configuration data.
    act: when the state is intialized from_charm.
    assert: InvalidStateError is raised.
    """
    harness.update_config(
        {"jenkins_url": "", "jenkins_agent_name": "", "jenkins_agent_token": "invalid"}
    )
    harness.begin()

    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm=harness.charm)


def test_from_charm_vailid_config(harness: ops.testing.Harness, config: typing.Dict[str, str]):
    """
    arrange: given valid charm configuration data.
    act: when thes tate is initialized from_charm.
    assert: valid charm state is returned.
    """
    harness.update_config(config)
    harness.begin()

    charm_state = state.State.from_charm(harness.charm)
    assert charm_state.jenkins_config, "Config should not be None."
    assert charm_state.jenkins_config.server_url == config["jenkins_url"]
    assert charm_state.jenkins_config.agent_names == [config["jenkins_agent_name"]]
    assert charm_state.jenkins_config.agent_tokens == [config["jenkins_agent_token"]]
