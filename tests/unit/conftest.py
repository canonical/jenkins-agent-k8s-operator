# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import pytest

from ops import testing

from charm import JenkinsAgentCharm


@pytest.fixture
def harness():
    """Creates test harness for unit tests."""
    # Create and confifgure harness
    harness = testing.Harness(JenkinsAgentCharm)
    harness.begin()
    harness.disable_hooks()
    harness.update_config(
        {
            "jenkins_url": "",
            "jenkins_agent_name": "",
            "jenkins_agent_token": "",
            "jenkins_agent_labels": "",
        }
    )

    yield harness

    harness.cleanup()
