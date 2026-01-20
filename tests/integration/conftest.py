# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Jenkins-agent-k8s-operator charm integration tests."""

import logging
import secrets
import typing

import jenkinsapi.jenkins
import kubernetes
import pytest
import pytest_asyncio
from juju.action import Action
from juju.application import Application
from juju.client._definitions import FullStatus, UnitStatus
from juju.model import Controller, Model
from juju.unit import Unit
from pytest import FixtureRequest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", name="charm")
async def charm_fixture(request: pytest.FixtureRequest, ops_test: OpsTest) -> str:
    """The path to charm."""
    charm = request.config.getoption("--charm-file")
    if not charm:
        charm = await ops_test.build_charm(".")
    else:
        charm = f"./{charm}"

    return charm


@pytest.fixture(scope="module", name="model")
def model_fixture(ops_test: OpsTest) -> Model:
    """The testing model."""
    assert ops_test.model
    return ops_test.model


@pytest.fixture(scope="module", name="kube_config")
def kube_config_fixture(request: FixtureRequest) -> str:
    """The kubernetes config file path."""
    kube_config = request.config.getoption("--kube-config")
    assert kube_config, (
        "--kube-confg argument is required which should contain the path to kube config."
    )
    return kube_config


@pytest.fixture(scope="module", name="kube_core_client")
def kube_core_client_fixture(kube_config: str) -> kubernetes.client.CoreV1Api:
    """Create a kubernetes client for core v1 API."""
    kubernetes.config.load_kube_config(config_file=kube_config)
    return kubernetes.client.CoreV1Api()


@pytest.fixture(scope="module", name="agent_image")
def agent_image_fixture(request: pytest.FixtureRequest) -> str:
    """The OCI image for jenkins-agent-k8s charm."""
    agent_k8s_image = request.config.getoption("--jenkins-agent-k8s-image")
    assert agent_k8s_image, (
        "--jenkins-agent-k8s-image argument is required which should contain the name of the OCI "
        "image."
    )
    return agent_k8s_image


@pytest.fixture(scope="module", name="num_agents")
def num_agents_fixture() -> int:
    """The number of agents to deploy."""
    return 1


@pytest_asyncio.fixture(scope="module", name="application")
async def application_fixture(
    model: Model, charm: str, agent_image: str, num_agents: int
) -> typing.AsyncGenerator[Application, None]:
    """Build and deploy the charm."""
    resources = {"jenkins-agent-k8s-image": agent_image}

    # Deploy the charm and wait for blocked status
    application = await model.deploy(
        charm, resources=resources, num_units=num_agents
    )
    await model.wait_for_idle(apps=[application.name], status="blocked")

    yield application

    await model.remove_application(application.name, block_until_done=True, force=True)


@pytest_asyncio.fixture(scope="module", name="machine_controller")
async def machine_controller_fixture() -> typing.AsyncGenerator[Controller, None]:
    """The juju controller on LXC local cloud."""
    controller = Controller()
    await controller.connect_controller("localhost")

    yield controller

    await controller.disconnect()


@pytest_asyncio.fixture(scope="module", name="machine_model")
async def machine_model_fixture(
    machine_controller: Controller,
) -> typing.AsyncGenerator[Model, None]:
    """The machine model for jenkins machine charm."""
    machine_model_name = f"jenkins-server-machine-{secrets.token_hex(2)}"
    logger.info("Adding model %s on cloud localhost", machine_model_name)
    model = await machine_controller.add_model(machine_model_name)

    yield model

    await model.disconnect()


@pytest_asyncio.fixture(scope="module", name="jenkins_machine_server")
async def jenkins_machine_server_fixture(machine_model: Model) -> Application:
    """The jenkins machine server."""
    app = await machine_model.deploy("jenkins", series="focal")
    await machine_model.wait_for_idle(apps=[app.name], timeout=1200, raise_on_error=False)

    return app


@pytest_asyncio.fixture(scope="module", name="machine_server_unit_ip")
async def machine_server_unit_ip_fixture(
    machine_model: Model, jenkins_machine_server: Application
):
    """Get Jenkins machine server charm unit IP."""
    status: FullStatus = await machine_model.get_status([jenkins_machine_server.name])
    application = typing.cast(Application, status.applications[jenkins_machine_server.name])
    try:
        unit_status: UnitStatus = next(iter(application.units.values()))
        assert unit_status.public_address, "Invalid unit address"
        return unit_status.public_address
    except StopIteration as exc:
        raise StopIteration("Invalid unit status") from exc


@pytest_asyncio.fixture(scope="module", name="machine_web_address")
async def machine_web_address_fixture(machine_server_unit_ip: str):
    """Get Jenkins machine server charm web address."""
    return f"http://{machine_server_unit_ip}:8080"


@pytest_asyncio.fixture(scope="module", name="machine_jenkins_client")
async def machine_jenkins_client_fixture(
    jenkins_machine_server: Application,
    machine_web_address: str,
) -> jenkinsapi.jenkins.Jenkins:
    """The Jenkins API client."""
    jenkins_unit: Unit = jenkins_machine_server.units[0]
    action: Action = await jenkins_unit.run_action("get-admin-credentials")
    await action.wait()
    assert action.status == "completed", "Failed to get credentials."
    password = action.results["password"]

    # Initialization of the jenkins client will raise an exception if unable to connect to the
    # server.
    return jenkinsapi.jenkins.Jenkins(
        baseurl=machine_web_address, username="admin", password=password, timeout=60
    )


@pytest_asyncio.fixture(scope="module", name="jenkins_k8s_server")
async def jenkins_k8s_server_fixture(model: Model) -> Application:
    """The jenkins k8s server."""
    # A custom JRE/Jenkins LTS upgraded version of Jenkins has been manually pushed to latest/edge
    # channel revision 128 for testing. There's a deadlock on the dependency in testing
    # jenkins-agent-k8s and jenkins-k8s.
    app = await model.deploy(
        "jenkins-k8s", series="jammy", channel="latest/edge", base="ubuntu@22.04", revision=128
    )
    await model.wait_for_idle(apps=[app.name], timeout=1200, raise_on_error=False, idle_period=30)

    return app


@pytest_asyncio.fixture(scope="module", name="k8s_server_unit_ip")
async def k8s_server_unit_ip_fixture(model: Model, jenkins_k8s_server: Application):
    """Get Jenkins k8s server charm unit IP."""
    status: FullStatus = await model.get_status([jenkins_k8s_server.name])
    application = typing.cast(Application, status.applications[jenkins_k8s_server.name])
    try:
        unit_status: UnitStatus = next(iter(application.units.values()))
        assert unit_status.address, "Invalid unit address"
        return unit_status.address
    except StopIteration as exc:
        raise StopIteration("Invalid unit status") from exc


@pytest_asyncio.fixture(scope="module", name="k8s_web_address")
async def k8s_web_address_fixture(k8s_server_unit_ip: str):
    """Get Jenkins k8s server charm web address."""
    return f"http://{k8s_server_unit_ip}:8080"


@pytest_asyncio.fixture(scope="module", name="jenkins_client")
async def jenkins_client_fixture(
    jenkins_k8s_server: Application,
    k8s_web_address: str,
) -> jenkinsapi.jenkins.Jenkins:
    """The Jenkins API client."""
    jenkins_unit: Unit = jenkins_k8s_server.units[0]
    action: Action = await jenkins_unit.run_action("get-admin-password")
    await action.wait()
    assert action.status == "completed", "Failed to get credentials."
    password = action.results["password"]

    # Initialization of the jenkins client will raise an exception if unable to connect to the
    # server.
    return jenkinsapi.jenkins.Jenkins(
        baseurl=k8s_web_address, username="admin", password=password, timeout=60
    )
