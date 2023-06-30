# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The agent pebble service module."""

import logging
import typing

import ops

import server
from state import State

logger = logging.getLogger(__name__)


class PebbleService(ops.Object):
    """The charm pebble service manager."""

    def __init__(self, charm: ops.CharmBase, state: State):
        """Initialize the pebble service.

        Args:
            charm: The parent Jenkins k8s agent charm.
            state: The Jenkins k8s agent state.
        """
        super().__init__(charm, "pebble-service")
        self.charm = charm
        self.state = state

    @property
    def _jenkins_agent_container(self) -> ops.Container:
        """The Jenkins workload container."""
        return self.charm.unit.get_container(self.state.jenkins_agent_service_name)

    def _get_pebble_layer(
        self, server_url: str, agent_token_pairs: typing.Iterable[typing.Tuple[str, str]]
    ) -> ops.pebble.Layer:
        """Return a dictionary representing a Pebble layer.

        Args:
            server_url: The Jenkins server address.
            agent_token_pairs: Matching pairs of agent name to agent token.

        Returns:
            The pebble layer defining Jenkins service layer.
        """
        layer: ops.pebble.LayerDict = {
            "summary": "Jenkins k8s agent layer",
            "description": "pebble config layer for Jenkins k8s agent.",
            "services": {
                self.state.jenkins_agent_service_name: {
                    "override": "replace",
                    "summary": "Jenkins k8s agent",
                    "command": str(server.ENTRYSCRIPT_PATH),
                    "environment": {
                        "JENKINS_URL": server_url,
                        "JENKINS_AGENTS": ":".join(pair[0] for pair in agent_token_pairs),
                        "JENKINS_TOKENS": ":".join(pair[1] for pair in agent_token_pairs),
                    },
                    "startup": "enabled",
                    "user": server.USER,
                    "group": server.GROUP,
                },
            },
            "checks": {
                "ready": {
                    "override": "replace",
                    "level": "ready",
                    "exec": {"command": "/bin/cat /var/lib/jenkins/agents/.ready"},
                    "period": "30s",
                    "threshold": 5,
                }
            },
        }
        return ops.pebble.Layer(layer)

    def reconcile(
        self, server_url: str, agent_token_pairs: typing.Iterable[typing.Tuple[str, str]]
    ) -> None:
        """Reconcile the Jenkins agent service.

        Args:
            server_url: The Jenkins server address.
            agent_token_pairs: Matching pairs of agent name to agent token.
        """
        self.charm.unit.status = ops.MaintenanceStatus("Starting agent pebble service.")

        agent_layer = self._get_pebble_layer(
            server_url=server_url, agent_token_pairs=agent_token_pairs
        )
        self._jenkins_agent_container.add_layer(
            label=self.state.jenkins_agent_service_name, layer=agent_layer, combine=True
        )
        self._jenkins_agent_container.replan()
        self.charm.unit.status = ops.ActiveStatus()

    def stop_agent(self):
        """Stop Jenkins agent."""
        if not self._jenkins_agent_container.can_connect():
            return
        self._jenkins_agent_container.stop(self.state.jenkins_agent_service_name)
        self._jenkins_agent_container.remove_path(str(server.AGENT_READY_PATH))
