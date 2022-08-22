# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

# Disable since pytest fixtures require the fixture name as an argument.
# pylint: disable=redefined-outer-name

"""Fixtures for integration tests."""

import pathlib
import subprocess

import jenkins
import pytest
import pytest_asyncio
import yaml
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module")
def jenkins_agent_image(pytestconfig: pytest.Config):
    """Get the jenkins agent image."""
    value: None | str = pytestconfig.getoption("--jenkins-agent-image")
    assert value is not None, "please specify the --jenkins-agent-image command line option"
    return value


@pytest.fixture(scope="module")
def jenkins_controller_name(pytestconfig: pytest.Config):
    """Get the name of the controller jenkins is running on."""
    value: None | str = pytestconfig.getoption("--jenkins-controller-name")
    assert value is not None, "please specify the --jenkins-controller-name command line option"
    return value


@pytest.fixture(scope="module")
def jenkins_model_name(pytestconfig: pytest.Config):
    """Get the name of the model jenkins is running on."""
    value: None | str = pytestconfig.getoption("--jenkins-model-name")
    assert value is not None, "please specify the --jenkins-model-name command line option"
    return value


@pytest.fixture(scope="module")
def jenkins_unit_number(pytestconfig: pytest.Config):
    """Get the number of the unit jenkins is running on."""
    value: None | str = pytestconfig.getoption("--jenkins-unit-number")
    assert value is not None, "please specify the --jenkins-unit-number command line option"
    assert value.isdigit(), "--jenkins-unit-number must be a non-negative integer"
    return int(value)


@pytest.fixture(scope="module")
def metadata():
    """Provides charm metadata."""
    yield yaml.safe_load(pathlib.Path("./metadata.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def app_name(metadata):
    """Provides app name from the metadata."""
    yield metadata["name"]


@pytest_asyncio.fixture(scope="module")
async def agent_label(ops_test: OpsTest):
    """Provides label that uniquely identifies the agent under test."""
    yield ops_test.model_name


@pytest_asyncio.fixture(scope="module")
async def app(
    ops_test: OpsTest,
    app_name: str,
    jenkins_agent_image: str,
    jenkins_controller_name: str,
    jenkins_model_name: str,
    agent_label: str,
):
    """Charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    # This helps with type hints, it seems model could be None
    assert ops_test.model is not None

    # Build and deploy the charm
    charm = await ops_test.build_charm(".")
    resources = {"jenkins-agent-image": jenkins_agent_image}
    application = await ops_test.model.deploy(
        charm,
        resources=resources,
        application_name=app_name,
        series="jammy",
        config={"jenkins_agent_labels": agent_label},
    )
    await ops_test.model.wait_for_idle()

    # Create the relationship
    jenkins_controller_model_name = f"{jenkins_controller_name}:{jenkins_model_name}"
    await ops_test.model.create_offer(application_name=app_name, endpoint=f"{app_name}:slave")
    subprocess.run(
        [
            "juju",
            "add-relation",
            "jenkins",
            f"micro:admin/{ops_test.model_name}.{app_name}",
            "--model",
            jenkins_controller_model_name,
        ],
        check=True,
    )
    await ops_test.model.wait_for_idle()

    yield application

    # Delete relation and saas
    subprocess.check_output(
        [
            "juju",
            "remove-relation",
            f"{app_name}:slave",
            "jenkins:master",
            "--model",
            jenkins_controller_model_name,
        ]
    )
    subprocess.check_output(
        ["juju", "remove-saas", app_name, "--model", jenkins_controller_model_name]
    )


@pytest.fixture(scope="module")
def jenkins_cli(jenkins_controller_name: str, jenkins_model_name: str, jenkins_unit_number: int):
    """Create cli to jenkins."""
    # Get information about jenkins
    unit_name = f"{jenkins_model_name}/{jenkins_unit_number}"
    controller_model_name = f"{jenkins_controller_name}:{jenkins_model_name}"
    result = subprocess.check_output(
        ["juju", "show-unit", unit_name, "--format", "yaml", "--model", controller_model_name]
    )
    public_address = yaml.safe_load(result)[unit_name]["public-address"]
    result = subprocess.check_output(
        [
            "juju",
            "run-action",
            unit_name,
            "get-admin-credentials",
            "--wait",
            "--format",
            "yaml",
            "--model",
            controller_model_name,
        ]
    )
    result_dict = yaml.safe_load(result)[f"unit-{unit_name.replace('/', '-')}"]["results"]
    username = result_dict["username"]
    password = result_dict["password"]

    # Create cli
    return jenkins.Jenkins(
        url=f"http://{public_address}:8080", username=username, password=password
    )


@pytest.fixture
def jenkins_test_job(jenkins_cli: jenkins.Jenkins, agent_label: str):
    """Create a test job."""
    job_name = f"test-job-{agent_label}"
    job_xml = f"""<?xml version='1.1' encoding='UTF-8'?>
<project>
  <description></description>
  <keepDependencies>false</keepDependencies>
  <properties/>
  <scm class="hudson.scm.NullSCM"/>
  <assignedNode>{agent_label}</assignedNode>
  <canRoam>false</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
  <triggers/>
  <concurrentBuild>false</concurrentBuild>
  <builders>
    <hudson.tasks.Shell>
      <command>echo test</command>
      <configuredLocalRules/>
    </hudson.tasks.Shell>
  </builders>
  <publishers/>
  <buildWrappers/>
</project>"""
    jenkins_cli.create_job(name=job_name, config_xml=job_xml)

    yield job_name

    jenkins_cli.delete_job(name=job_name)
