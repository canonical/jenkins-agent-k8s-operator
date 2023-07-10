# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Jenkins-k8s-agent state module tests."""

# Need access to protected functions for testing
# pylint:disable=protected-access

import os
import typing
import unittest.mock

import ops
import ops.testing
import pytest

import state


def test__get_jenkins_unit():
    """
    arrange: given a set of units in a relation.
    act: when _get_jenkins_units is called.
    assert: the Jenkins server unit is returned.
    """
    agent_app_name = "jenkins-agent-k8s"
    mock_agent_unit = unittest.mock.MagicMock(spec=ops.Unit)
    mock_agent_unit_2 = unittest.mock.MagicMock(spec=ops.Unit)
    mock_agent_app = unittest.mock.MagicMock(spec=ops.Application)
    mock_agent_app.name = agent_app_name
    mock_agent_unit.app = mock_agent_app
    mock_agent_unit_2.app = mock_agent_app
    mock_server_unit = unittest.mock.MagicMock(spec=ops.Unit)
    mock_server_app = unittest.mock.MagicMock(spec=ops.Application)
    mock_server_unit.app = mock_server_app
    mock_server_app.name = "jenkins"

    assert (
        state._get_jenkins_unit(
            set((mock_agent_unit, mock_server_unit, mock_agent_unit_2)),
            current_app_name=agent_app_name,
        )
        == mock_server_unit
    )


def test_from_charm_invalid_agent_data(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given an invalid os cpu_count data.
    act: when the state is initialized from_charm.
    assert: InvalidStateError is raised.
    """
    monkeypatch.setattr(os, "cpu_count", lambda: 0)
    mock_charmbase = unittest.mock.MagicMock(spec=ops.CharmBase)
    with pytest.raises(state.InvalidStateError):
        state.State.from_charm(charm=mock_charmbase)


def test_from_charm_invalid_charm_config(harness: ops.testing.Harness):
    """
    arrange: given an invalid charm configuration data.
    act: when the state is initialized from_charm.
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
    act: when the state is initialized from_charm.
    assert: valid charm state is returned.
    """
    harness.update_config(config)
    harness.begin()

    charm_state = state.State.from_charm(harness.charm)
    assert charm_state.jenkins_config, "Config should not be None."
    assert charm_state.jenkins_config.server_url == config["jenkins_url"]
    assert charm_state.jenkins_config.agent_name_token_pairs == [
        (config["jenkins_agent_name"], config["jenkins_agent_token"])
    ]
