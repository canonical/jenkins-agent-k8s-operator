# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Jenkins-agent-k8s-operator charm integration tests."""

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


@pytest_asyncio.fixture(scope="module", name="application")
async def application_fixture(
    ops_test: OpsTest, model: Model, agent_image: str
) -> typing.AsyncGenerator[Application, None]:
    """Build and deploy the charm."""
    # Build and deploy charm from local source folder
    charm = await ops_test.build_charm(".")
    resources = {"jenkins-agent-k8s-image": agent_image}

    # Deploy the charm and wait for active/idle status
    application = await model.deploy(charm, resources=resources, series="jammy")
    await model.wait_for_idle(apps=[application.name], status="active", raise_on_blocked=True)

    yield application

    await model.remove_application(application.name, block_until_done=True)


@pytest_asyncio.fixture(scope="module", name="machine_controller")
async def machine_controller_fixture() -> typing.AsyncGenerator[Controller, None]:
    """The lxd controller."""
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
    model = await machine_controller.add_model(machine_model_name)

    yield model

    await model.disconnect()


@pytest_asyncio.fixture(scope="module", name="jenkins_machine_server")
async def jenkins_machine_server_fixture(machine_model: Model) -> Application:
    """The jenkins machine server."""
    app = await machine_model.deploy("jenkins", channel="latest/edge", series="focal")
    await machine_model.wait_for_idle(apps=[app.name], status="blocked", timeout=1200)

    return app


@pytest_asyncio.fixture(scope="module", name="server_unit_ip")
async def server_unit_ip_fixture(machine_model: Model, jenkins_machine_server: Application):
    """Get Jenkins machine server charm unit IP."""
    status: FullStatus = await machine_model.get_status([jenkins_machine_server.name])
    try:
        unit_status: UnitStatus = next(
            iter(status.applications[jenkins_machine_server.name].units.values())
        )
        assert unit_status.address, "Invalid unit address"
        return unit_status.address
    except StopIteration as exc:
        raise StopIteration("Invalid unit status") from exc


@pytest_asyncio.fixture(scope="module", name="web_address")
async def web_address_fixture(unit_ip: str):
    """Get Jenkins machine server charm web address."""
    return f"http://{unit_ip}:8080"


@pytest_asyncio.fixture(scope="module", name="jenkins_client")
async def jenkins_client_fixture(
    jenkins_machine_server: Application,
    web_address: str,
) -> jenkinsapi.jenkins.Jenkins:
    """The Jenkins API client."""
    jenkins_unit: Unit = jenkins_machine_server.units[0]
    action: Action = await jenkins_unit.run_action("get-admin-credentials")
    await action.wait()
    password = action.results["password"]

    # Initialization of the jenkins client will raise an exception if unable to connect to the
    # server.
    return jenkinsapi.jenkins.Jenkins(
        baseurl=web_address, username="admin", password=password, timeout=60
    )
