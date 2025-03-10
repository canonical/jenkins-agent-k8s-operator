# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The agent pebble service module."""

import logging
import typing

import ops

import server
from state import State

logger = logging.getLogger(__name__)


class PebbleService:
    """The charm pebble service manager."""

    def __init__(self, state: State):
        """Initialize the pebble service.

        Args:
            state: The Jenkins agent k8s state.
        """
        self.state = state

    def _get_pebble_layer(
        self, server_url: str, agent_token_pair: typing.Tuple[str, str]
    ) -> ops.pebble.Layer:
        """Return a dictionary representing a Pebble layer.

        Args:
            server_url: The Jenkins server address.
            agent_token_pair: Matching pair of agent name to agent token.

        Returns:
            The pebble layer defining Jenkins service layer.
        """
        layer: ops.pebble.LayerDict = {
            "summary": "Jenkins agent k8s layer",
            "description": "pebble config layer for Jenkins agent k8s.",
            "services": {
                self.state.jenkins_agent_service_name: {
                    "override": "replace",
                    "summary": "Jenkins agent k8s",
                    "command": str(server.ENTRYSCRIPT_PATH),
                    "environment": {
                        "JENKINS_URL": server_url,
                        "JENKINS_AGENT": agent_token_pair[0],
                        "JENKINS_TOKEN": agent_token_pair[1],
                    },
                    "startup": "enabled",
                    "user": server.USER,
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
        self, server_url: str, agent_token_pair: typing.Tuple[str, str], container: ops.Container
    ) -> None:
        """Reconcile the Jenkins agent service.

        Args:
            server_url: The Jenkins server address.
            agent_token_pair: Matching pair of agent name to agent token.
            container: The agent workload container.
        """
        agent_layer = self._get_pebble_layer(
            server_url=server_url, agent_token_pair=agent_token_pair
        )
        container.add_layer(
            label=self.state.jenkins_agent_service_name, layer=agent_layer, combine=True
        )
        container.replan()

    def stop_agent(self, container: ops.Container) -> None:
        """Stop Jenkins agent.

        Args:
            container: The agent workload container.
        """
        try:
            # use get_service to check if service should be stopped rather than stopping and
            # catching ops.pebble.APIError and parsing error message to determine type of error.
            container.get_service(self.state.jenkins_agent_service_name)
        except ops.ModelError:
            return
        container.stop(self.state.jenkins_agent_service_name)
        container.remove_path(str(server.AGENT_READY_PATH))
