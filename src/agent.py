# Copyright 2023 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

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
            charm.on[SLAVE_RELATION].relation_joined, self._on_agent_relation_joined
        )
        charm.framework.observe(
            charm.on[SLAVE_RELATION].relation_changed, self._on_agent_relation_changed
        )
        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_joined, self._on_agent_relation_joined
        )
        charm.framework.observe(
            charm.on[AGENT_RELATION].relation_changed, self._on_agent_relation_changed
        )

    @property
    def _jenkins_agent_container(self) -> ops.Container:
        """The Jenkins workload container."""
        return self.charm.unit.get_container(self.state.jenkins_agent_service_name)

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
        self.charm.unit.status = ops.MaintenanceStatus("Setting up relation.")

        # handle slave relation for backwards compatibility.
        if event.relation.name == SLAVE_RELATION:
            logger.info(
                "Slave relation data set: %s",
                self.state.agent_meta.get_jenkins_slave_interface_dict(),
            )
            event.relation.data[self.charm.unit].update(
                self.state.agent_meta.get_jenkins_slave_interface_dict()
            )
            return
        logger.info(
            "Agent relation data set: %s",
            self.state.agent_meta.get_jenkins_slave_interface_dict(),
        )
        event.relation.data[self.charm.unit].update(
            self.state.agent_meta.get_jenkins_agent_v0_interface_dict()
        )

    def _on_agent_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Handle agent relation changed event.

        Args:
            event: The event fired when the event relation data has changed.
        """
        logger.info("%s relation changed.", event.relation.name)

        if self.state.jenkins_config:
            logger.warning(
                "Jenkins configuration already exists. Ignoring %s relation.", event.relation.name
            )
            return

        if not self._jenkins_agent_container.can_connect():
            logger.warning("Jenkins agent container not yet ready. Deferring.")
            event.defer()
            return

        if server.is_registered(self._jenkins_agent_container):
            logger.warning("Given agent already registered. Skipping.")
            return

        server_data: typing.Optional[server.Credentials] = server.get_credentials(
            event.relation.name,
            unit_name=self.state.agent_meta.name,
            databag=event.relation.data.get(typing.cast(ops.Unit, event.unit)),
        )
        if not server_data:
            self.charm.unit.status = ops.WaitingStatus("Waiting for complete relation data.")
            logger.info("Waiting for complete relation data.")
            return

        self.charm.unit.status = ops.MaintenanceStatus("Downloading Jenkins agent executable.")
        try:
            server.download_jenkins_agent(
                server_url=server_data.address, connectable_container=self._jenkins_agent_container
            )
        except server.AgentJarDownloadError as exc:
            logger.error("Failed to download Jenkins agent executable, %s", exc)
            self.charm.unit.status = ops.BlockedStatus(
                "Failed to download Jenkins agent executable."
            )

        self.charm.unit.status = ops.MaintenanceStatus("Validating credentials.")
        if not server.validate_credentials(
            agent_name=self.state.agent_meta.name,
            credentials=server_data,
            connectable_container=self._jenkins_agent_container,
        ):
            logger.warning("Failed credential for agent %s", self.state.agent_meta.name)
            return

        self.pebble_service.reconcile(
            server_url=server_data.address,
            agent_token_pairs=((self.state.agent_meta.name, server_data.secret),),
        )
