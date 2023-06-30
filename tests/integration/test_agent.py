# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for jenkins-agent-k8s-operator charm."""


from juju.application import Application
from juju.model import Model


async def test_agent_relation(
    jenkins_machine_server: Application,
    application: Application,
):
    """
    arrange: given a cross controller cross model jenkins machine agent.
    act: when the offer is created and relation is setup through the offer.
    assert: the relation succeeds and agents become active.
    """
    machine_model: Model = jenkins_machine_server.model
    machine_model.create_offer(f"{jenkins_machine_server.name}:master")
    model: Model = application.model
    await model.relate(
        f"{application.name}:agent",
        f"localhost:admin/{machine_model.name}.{application.name}",
    )
    await model.wait_for_idle(status="active", timeout=1200)
