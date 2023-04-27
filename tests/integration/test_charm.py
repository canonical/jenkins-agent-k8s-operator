#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the charm."""

import asyncio

import jenkins
import pytest
from ops.model import ActiveStatus


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_active(app):
    """
    arrange: given charm that has been built and deployed and related to jenkins
    act: when the unit status is checked
    assert: then it is in the active state.
    """
    assert app.units[0].workload_status == ActiveStatus.name


# Disabling unused-argument because the fixture is required even though the test doesn't use it
@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_build_succeeds(
    app,  # pylint: disable=unused-argument
    jenkins_cli: jenkins.Jenkins,
    jenkins_test_job: str,
):
    """
    arrange: given charm that has been built, deployed and related to jenkins and a job that has
        been created in jenkins targeting the agent
    act: when the build is executed
    assert: then the build finishes successfully.
    """
    jenkins_cli.build_job(jenkins_test_job)
    # Wait for build to finish
    for _ in range(100):
        if jenkins_cli.get_job_info(jenkins_test_job)["lastCompletedBuild"] is not None:
            break
        await asyncio.sleep(1)

    assert (
        jenkins_cli.get_job_info(jenkins_test_job)["lastCompletedBuild"] is not None
    ), "job did not run"
    assert "Finished: SUCCESS" in jenkins_cli.get_build_console_output(
        jenkins_test_job,
        jenkins_cli.get_job_info(jenkins_test_job)["lastCompletedBuild"]["number"],
    )
