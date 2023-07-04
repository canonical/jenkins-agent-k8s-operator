# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The agent relation observer module."""

import logging
import typing

import ops

import pebble
import server
from state import AGENT_RELATION, SLAVE_RELATION, State

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
            charm.on[SLAVE_RELATION].relation_joined, self._on_slave_relation_joined
        )
        charm.framework.observe(
            charm.on[SLAVE_RELATION].relation_changed, self._on_slave_relation_changed
        )
        charm.framework.observe(
            charm.on[SLAVE_RELATION].relation_departed, self._on_slave_relation_departed
        )
        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_joined, self._on_agent_relation_joined
        )
        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_changed, self._on_agent_relation_changed
        )
        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_departed, self._on_agent_relation_departed
        )

    def _on_slave_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Handle slave relation joined event.

        Args:
            event: The event fired when an agent has joined the "slave" relation.
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

        relation_data = self.state.agent_meta.get_jenkins_slave_interface_dict()
        logger.info("Slave relation data set: %s", relation_data)
        event.relation.data[self.charm.unit].update(relation_data)

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
        logger.info("Agent relation data set: %s", relation_data)
        event.relation.data[self.charm.unit].update(relation_data)

    def _on_slave_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle slave relation changed event.

        Args:
            event: The event fired when slave relation data has changed.
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

        if server.is_registered(container):
            logger.warning("Given agent already registered. Skipping.")
            return

        credentials: typing.Optional[server.Credentials] = server.get_credentials(
            event.relation.name,
            unit_name=self.state.agent_meta.name,
            databag=event.relation.data.get(typing.cast(ops.Unit, event.unit)),
        )
        if not credentials:
            self.charm.unit.status = ops.WaitingStatus("Waiting for complete relation data.")
            logger.info("Waiting for complete relation data.")
            return

        self.charm.unit.status = ops.MaintenanceStatus("Validating credentials.")
        if not server.validate_credentials(
            agent_name=self.state.agent_meta.name,
            credentials=credentials,
            container=container,
            add_random_delay=True,
        ):
            logger.warning("Failed credential for agent %s", self.state.agent_meta.name)
            self.charm.unit.status = ops.WaitingStatus("Waiting for credentials.")
            return

        self.pebble_service.reconcile(
            server_url=credentials.address,
            agent_token_pair=(self.state.agent_meta.name, credentials.secret),
        )

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

        if server.is_registered(container):
            logger.warning("Given agent already registered. Skipping.")
            return

        credentials: typing.Optional[server.Credentials] = server.get_credentials(
            event.relation.name,
            unit_name=self.state.agent_meta.name,
            databag=event.relation.data.get(typing.cast(ops.Unit, event.unit)),
        )
        if not credentials:
            self.charm.unit.status = ops.WaitingStatus("Waiting for complete relation data.")
            logger.info("Waiting for complete relation data.")
            return

        self.charm.unit.status = ops.MaintenanceStatus("Downloading Jenkins agent executable.")
        try:
            server.download_jenkins_agent(server_url=credentials.address, container=container)
        except server.AgentJarDownloadError as exc:
            logger.error("Failed to download Jenkins agent executable, %s", exc)
            self.charm.unit.status = ops.BlockedStatus(
                "Failed to download Jenkins agent executable."
            )
            return

        self.charm.unit.status = ops.MaintenanceStatus("Validating credentials.")
        if not server.validate_credentials(
            agent_name=self.state.agent_meta.name,
            credentials=credentials,
            container=container,
        ):
            logger.warning("Failed credential for agent %s", self.state.agent_meta.name)
            self.charm.unit.status = ops.WaitingStatus("Waiting for credentials.")
            return

        self.pebble_service.reconcile(
            server_url=credentials.address,
            agent_token_pair=(self.state.agent_meta.name, credentials.secret),
        )

    def _on_slave_relation_departed(self, _: ops.RelationDepartedEvent) -> None:
        """Handle slave relation departed event."""
        container = self.charm.unit.get_container(self.state.jenkins_agent_service_name)
        if not container.can_connect():
            return
        self.pebble_service.stop_agent()
        self.charm.unit.status = ops.BlockedStatus("Waiting for config/relation.")

    def _on_agent_relation_departed(self, _: ops.RelationDepartedEvent) -> None:
        """Handle agent relation departed event."""
        container = self.charm.unit.get_container(self.state.jenkins_agent_service_name)
        if not container.can_connect():
            return
        self.pebble_service.stop_agent()
        self.charm.unit.status = ops.BlockedStatus("Waiting for config/relation.")
