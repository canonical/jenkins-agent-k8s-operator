# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for jenkins-agent-k8s-operator charm."""

import logging

import jenkinsapi.jenkins
from juju.application import Application
from juju.model import Model

logger = logging.getLogger()


async def test_agent_relation(
    jenkins_machine_server: Application,
    application: Application,
    jenkins_client: jenkinsapi.jenkins.Jenkins,
):
    """
    arrange: given a cross controller cross model jenkins machine agent.
    act: when the offer is created and relation is setup through the offer.
    assert: the relation succeeds and agents become active.
    """
    machine_model: Model = jenkins_machine_server.model
    logger.info(f"Creating offer {jenkins_machine_server.name}:master")
    await machine_model.create_offer(f"{jenkins_machine_server.name}:master")
    model: Model = application.model
    logger.info(
        "Relating %s:agent localhost:admin/%s.%s",
        application.name,
        machine_model.name,
        jenkins_machine_server.name,
    )
    await model.relate(
        f"{application.name}:slave",
        f"localhost:admin/{machine_model.name}.{jenkins_machine_server.name}",
    )
    await model.wait_for_idle(status="active", timeout=1200)

    nodes = jenkins_client.get_nodes()
    assert all(node.is_online() for node in nodes.values())
