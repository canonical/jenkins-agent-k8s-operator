# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Jenkins-agent-k8s-operator charm integration tests."""

import secrets
import typing

import ops
import ops.testing
import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Controller, Model
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module", name="model")
def model_fixture(ops_test: OpsTest) -> ops.Model:
    """The testing model."""
    assert ops_test.model
    return ops_test.model


@pytest.fixture(scope="module", name="agent_image")
def agent_image_fixture(request: pytest.FixtureRequest) -> str:
    """The OCI image for jenkins-agent-k8s charm."""
    agent_k8s_image = request.config.getoption("--jenkins-agent-k8s-image")
    assert (
        agent_k8s_image
    ), "--jenkins-agent-k8s-image argument is required which should contain the name of the OCI image."
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
    machine_model_name = f"jenkins-agent-machine-{secrets.token_hex(2)}"
    model = await machine_controller.add_model(machine_model_name)

    yield model

    await model.disconnect()


@pytest_asyncio.fixture(scope="module", name="jenkins_machine_server")
async def jenkins_machine_server_fixture(machine_model: Model) -> Application:
    """The jenkins machine server."""
    app = await machine_model.deploy("jenkins", channel="latest/stable", series="focal")
    await machine_model.wait_for_idle(apps=[app.name], status="blocked", timeout=1200)

    return app
