# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for jenkins-agent-k8s-operator charm with k8s server."""

import contextlib
import logging

import jenkinsapi.custom_exceptions
import jenkinsapi.jenkins
import kubernetes
import requests.exceptions
from juju.application import Application
from juju.errors import JujuError
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
    await wait_for(lambda: not node.is_online(), timeout=60 * 10, check_interval=5)

    def containers_ready() -> bool:
        """Check if all containers are ready.

        Returns:
            True if containers are all ready.
        """
        pod_status: kubernetes.client.V1PodStatus = kube_core_client.read_namespaced_pod_status(
            name=pod_name, namespace=model.name
        ).status
        container_statuses: list[kubernetes.client.V1ContainerStatus] = (
            pod_status.container_statuses
        )
        return all(status.ready for status in container_statuses)

    await wait_for(containers_ready, timeout=60 * 10)
    await wait_for(node.is_online, timeout=60 * 10)
    assert node.is_online(), "Node not online."


async def test_agent_run_sudo(
    application: Application,
):
    """
    arrange: given a jenkins-agent-k8s charm.
    act: Check if the _daemon_ user is allowed to run sudo commands.
    assert: the _daemon_ user has the correct sudo privileges.
    """
    unit = application.units[0]
    pebble_exec = (
        "PEBBLE_SOCKET=/charm/containers/jenkins-agent-k8s/pebble.socket "
        "pebble exec --user=_daemon_"
    )
    full_command = f"{pebble_exec} -- sudo -l"
    logger.info("Enable plugins command: %s", full_command)

    action = await unit.run(full_command)
    await action.wait()

    assert action.results["return-code"] == 0, action.results["stderr"]
    assert "NOPASSWD" in action.results["stdout"]


def _agent_is_online(client: jenkinsapi.jenkins.Jenkins, agent_name: str) -> bool:
    """Check if agent node is online.

    Args:
        client: Jenkins API client.
        agent_name: The agent node name.

    Returns:
        True if the agent is online.
    """
    try:
        node = client.get_node(agent_name)
        return node.is_online()
    except (
        jenkinsapi.custom_exceptions.JenkinsAPIException,
        requests.exceptions.RequestException,
    ):
        return False


async def test_agent_reconnects_after_server_refresh(
    model: Model,
    application: Application,
    jenkins_k8s_server: Application,
    jenkins_client: jenkinsapi.jenkins.Jenkins,
):
    """
    arrange: given a jenkins-agent-k8s charm related to jenkins-k8s server with agent online.
    act: when the Jenkins server charm is refreshed (simulating a pod restart / URL change).
    assert: the agent automatically reconnects and comes back online.
    """
    # Ensure relation exists (may already be established from test_agent_recover).
    with contextlib.suppress(JujuError):  # Relation already exists from earlier test.
        await model.relate(f"{application.name}:agent", f"{jenkins_k8s_server.name}:agent")
    await model.wait_for_idle(
        apps=[application.name, jenkins_k8s_server.name],
        status="active",
        timeout=60 * 15,
    )

    agent_unit: Unit = next(iter(application.units))
    pod_name = agent_unit.name.replace("/", "-")

    # Verify agent is initially online.
    node: jenkinsapi.node.Node = jenkins_client.get_node(pod_name)
    assert node.is_online(), f"Agent {pod_name} should be online before server refresh"

    # Refresh the Jenkins server charm to trigger pod restart / IP change.
    logger.info("Refreshing jenkins-k8s server charm...")
    await jenkins_k8s_server.refresh(channel="latest/edge")
    await model.wait_for_idle(
        apps=[jenkins_k8s_server.name],
        timeout=60 * 15,
        raise_on_error=False,
        idle_period=30,
    )

    # Get new Jenkins server address after refresh.
    server_unit: Unit = next(iter(jenkins_k8s_server.units))
    action = await server_unit.run_action("get-admin-password")
    await action.wait()
    assert action.status == "completed", "Failed to get credentials after refresh."
    new_password = action.results["password"]

    # Find new server IP.
    status = await model.get_status([jenkins_k8s_server.name])
    server_app_status = status.applications[jenkins_k8s_server.name]
    assert server_app_status is not None, "Server application status not found."
    server_unit_status = next(iter(server_app_status.units.values()))
    assert server_unit_status is not None, "Server unit status not found."
    new_address = str(server_unit_status.address)
    logger.info("Jenkins server new address after refresh: %s", new_address)

    new_client = jenkinsapi.jenkins.Jenkins(
        baseurl=f"http://{new_address}:8080",
        username="admin",
        password=new_password,
        timeout=60,
    )

    # Wait for the model to settle (agent charm should detect URL change and reconnect).
    await model.wait_for_idle(
        apps=[application.name, jenkins_k8s_server.name],
        status="active",
        timeout=60 * 15,
    )

    # Wait for agent to come back online on the new Jenkins instance.
    await wait_for(
        lambda: _agent_is_online(new_client, pod_name),
        timeout=60 * 10,
        check_interval=10,
    )

    node = new_client.get_node(pod_name)
    assert node.is_online(), f"Agent {pod_name} should be online after server refresh"
