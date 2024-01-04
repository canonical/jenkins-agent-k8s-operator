# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for jenkins-agent-k8s-operator charm with k8s server."""


import logging

import jenkinsapi.jenkins
import kubernetes
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

from .helpers import wait_for

logger = logging.getLogger()


async def test_agent_recover(
    kube_core_client: kubernetes.client.CoreV1Api,
    model: Model,
    application: Application,
    jenkins_k8s_server: Application,
    jenkins_client: jenkinsapi.jenkins.Jenkins,
):
    """
    arrange: given a jenkins-agent-k8s charm that is related to jenkins-k8s charm.
    act: when a pod is removed (restarted by kubernetes by default).
    assert: the agent automatically re-registers itself.
    """
    await model.relate(f"{application.name}:agent", f"{jenkins_k8s_server.name}:agent")
    await model.wait_for_idle(
        apps=[application.name, jenkins_k8s_server.name], wait_for_active=True
    )
    agent_unit: Unit = next(iter(application.units))
    pod_name = agent_unit.name.replace("/", "-")
    node: jenkinsapi.node.Node = jenkins_client.get_node(pod_name)
    assert node.is_online(), "Node not online."

    kube_core_client.delete_namespaced_pod(name=pod_name, namespace=model.name)
    await wait_for(lambda: not node.is_online(), timeout=60 * 10)

    def containers_ready() -> bool:
        """Check if all containers are ready.

        Returns:
            True if containers are all ready.
        """
        pod_status: kubernetes.client.V1PodStatus = kube_core_client.read_namespaced_pod_status(
            name=pod_name, namespace=model.name
        ).status
        container_statuses: list[
            kubernetes.client.V1ContainerStatus
        ] = pod_status.container_statuses
        return all(status.ready for status in container_statuses)

    await wait_for(containers_ready, timeout=60 * 10)
    await wait_for(node.is_online, timeout=60 * 10)
    assert node.is_online(), "Node not online."
