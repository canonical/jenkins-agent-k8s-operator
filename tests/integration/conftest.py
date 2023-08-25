# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Jenkins-agent-k8s-operator charm integration tests."""

import logging
import secrets
import typing

import jenkinsapi.jenkins
import pytest
import pytest_asyncio
from juju.action import Action
from juju.application import Application
from juju.client._definitions import FullStatus, UnitStatus
from juju.model import Controller, Model
from juju.unit import Unit
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
    ops_test: OpsTest, model: Model, charm: str, agent_image: str, num_agents: int
) -> typing.AsyncGenerator[Application, None]:
    """Build and deploy the charm."""
    resources = {"jenkins-agent-k8s-image": agent_image}

    # Deploy the charm and wait for blocked status
    application = await model.deploy(
        charm, resources=resources, series="jammy", num_units=num_agents
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


@pytest_asyncio.fixture(scope="module", name="server_unit_ip")
async def server_unit_ip_fixture(machine_model: Model, jenkins_machine_server: Application):
    """Get Jenkins machine server charm unit IP."""
    status: FullStatus = await machine_model.get_status([jenkins_machine_server.name])
    try:
        unit_status: UnitStatus = next(
            iter(status.applications[jenkins_machine_server.name].units.values())
        )
        assert unit_status.public_address, "Invalid unit address"
        return unit_status.public_address
    except StopIteration as exc:
        raise StopIteration("Invalid unit status") from exc


@pytest_asyncio.fixture(scope="module", name="web_address")
async def web_address_fixture(server_unit_ip: str):
    """Get Jenkins machine server charm web address."""
    return f"http://{server_unit_ip}:8080"


@pytest_asyncio.fixture(scope="module", name="jenkins_client")
async def jenkins_client_fixture(
    jenkins_machine_server: Application,
    web_address: str,
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
        baseurl=web_address, username="admin", password=password, timeout=60
    )
