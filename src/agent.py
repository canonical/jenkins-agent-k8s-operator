# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The agent relation observer module."""

import logging

import ops

import pebble
import server
from state import AGENT_RELATION, State

logger = logging.getLogger()


class Observer(ops.Object):
    """The Jenkins agent relation observer."""

    def __init__(self, charm: ops.CharmBase, state: State, pebble_service: pebble.PebbleService):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
            state: The charm state.
            pebble_service: Service manager that controls Jenkins agent service through pebble.
        """
        super().__init__(charm, "agent-observer")
        self.charm = charm
        self.state = state
        self.pebble_service = pebble_service

        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_joined, self._on_agent_relation_joined
        )
        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_changed, self._on_agent_relation_changed
        )
        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_departed, self._on_agent_relation_departed
        )

    def _on_agent_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Handle agent relation joined event.

        Args:
            event: The event fired when an agent has joined the relation.
        """
        if self.state.jenkins_config:
            logger.warning(
                "Jenkins configuration already exists. Ignoring %s relation.", event.relation.name
            )
            return

        logger.info("%s relation joined.", event.relation.name)
        self.charm.unit.status = ops.MaintenanceStatus(
            f"Setting up '{event.relation.name}' relation."
        )

        relation_data = self.state.agent_meta.get_jenkins_agent_v0_interface_dict()
        logger.debug("Agent relation data set: %s", relation_data)
        event.relation.data[self.charm.unit].update(relation_data)

    def _on_agent_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle agent relation changed event.

        Args:
            event: The event fired when the agent relation data has changed.
        """
        logger.info("%s relation changed.", event.relation.name)

        if self.state.jenkins_config:
            logger.warning(
                "Jenkins configuration already exists. Ignoring %s relation.", event.relation.name
            )
            return

        container = self.charm.unit.get_container(self.state.jenkins_agent_service_name)
        if not container.can_connect():
            logger.warning("Jenkins agent container not yet ready. Deferring.")
            event.defer()
            return

        # Check if the pebble service has started and set agent ready.
        if container.exists(str(server.AGENT_READY_PATH)):
            logger.warning("Given agent already registered. Skipping.")
            return

        if not self.state.agent_relation_credentials:
            self.charm.unit.status = ops.WaitingStatus("Waiting for complete relation data.")
            logger.info("Waiting for complete relation data.")
            # The event needs to be retried after the agent credentials have been set.
            event.defer()
            return

        self.start_agent_from_relation(
            container=container,
            credentials=self.state.agent_relation_credentials,
            agent_name=self.state.agent_meta.name,
        )

    def start_agent_from_relation(
        self, container: ops.Container, credentials: server.Credentials, agent_name: str
    ) -> None:
        """Start agent from agent relation.

        Args:
            container: The Jenkins agent workload container.
            credentials: The agent registration details for jenkins server.
            agent_name: The jenkins agent to register as.

        Raises:
            AgentJarDownloadError: if the agent jar executable failed to download.
        """
        self.charm.unit.status = ops.MaintenanceStatus("Downloading Jenkins agent executable.")
        try:
            server.download_jenkins_agent(server_url=credentials.address, container=container)
        except server.AgentJarDownloadError as exc:
            logger.error("Failed to download Jenkins agent executable, %s", exc)
            raise server.AgentJarDownloadError("Failed to download Jenkins agent.") from exc

        self.charm.unit.status = ops.MaintenanceStatus("Starting agent pebble service.")
        self.pebble_service.reconcile(
            server_url=credentials.address,
            agent_token_pair=(
                agent_name,
                credentials.secret,
            ),
            container=container,
        )
        self.charm.unit.status = ops.ActiveStatus()

    def _on_agent_relation_departed(self, _: ops.RelationDepartedEvent) -> None:
        """Handle agent relation departed event."""
        container = self.charm.unit.get_container(self.state.jenkins_agent_service_name)
        if not container.can_connect():
            logger.warning("Relation departed before service ready.")
            return
        self.pebble_service.stop_agent(container=container)
        self.charm.unit.status = ops.BlockedStatus("Waiting for config/relation.")
