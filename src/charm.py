#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm k8s jenkins agent."""

import logging
import typing

import ops
from ops.main import main

import pebble
import server
from state import AGENT_RELATION, InvalidStateError, State

logger = logging.getLogger()


class JenkinsAgentCharm(ops.CharmBase):
    """Charm Jenkins agent k8s.

    Uses a reconciliation pattern: all events funnel to _reconcile() which
    computes the desired state from current reality and applies it idempotently.
    """

    def __init__(self, *args: typing.Any):
        """Initialize the charm and register event handlers.

        Args:
            args: Arguments to initialize the charm base.
        """
        super().__init__(*args)

        # All events converge on the same reconcile handler.
        self.framework.observe(self.on.config_changed, self._on_reconcile)
        self.framework.observe(self.on.upgrade_charm, self._on_reconcile)
        self.framework.observe(self.on.jenkins_agent_k8s_pebble_ready, self._on_reconcile)
        self.framework.observe(
            self.on[AGENT_RELATION].relation_joined, self._on_agent_relation_joined
        )
        self.framework.observe(self.on[AGENT_RELATION].relation_changed, self._on_reconcile)
        self.framework.observe(
            self.on[AGENT_RELATION].relation_departed, self._on_agent_relation_departed
        )

    def _on_agent_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Publish agent metadata into the relation databag.

        Args:
            event: The event fired when an agent has joined the relation.
        """
        try:
            state = State.from_charm(self)
        except InvalidStateError as exc:
            self.unit.status = ops.BlockedStatus(exc.msg)
            return

        if state.jenkins_config:
            logger.warning(
                "Jenkins configuration already exists. Ignoring %s relation.",
                event.relation.name,
            )
            return

        logger.info("%s relation joined.", event.relation.name)
        self.unit.status = ops.MaintenanceStatus(f"Setting up '{event.relation.name}' relation.")
        relation_data = state.agent_meta.get_jenkins_agent_v0_interface_dict()
        logger.debug("Agent relation data set: %s", relation_data)
        event.relation.data[self.unit].update(relation_data)

    def _on_agent_relation_departed(self, event: ops.RelationDepartedEvent) -> None:
        """Stop the agent when the relation is removed.

        Args:
            event: The event fired when the relation is departing.
        """
        try:
            state = State.from_charm(self)
        except InvalidStateError as exc:
            self.unit.status = ops.BlockedStatus(exc.msg)
            return

        container = self.unit.get_container(state.jenkins_agent_service_name)
        if not container.can_connect():
            logger.warning("Relation departed before service ready.")
            return
        pebble_service = pebble.PebbleService(state)
        pebble_service.stop_agent(container=container)
        self.unit.status = ops.BlockedStatus("Waiting for config/relation.")

    def _on_reconcile(self, event: ops.EventBase) -> None:
        """Single reconciliation entry point for all state-convergence events.

        Computes the desired agent state from current reality (config, relation
        data, container readiness) and drives towards it idempotently.

        Args:
            event: Any event that should trigger reconciliation.
        """
        try:
            state = State.from_charm(self)
        except InvalidStateError as exc:
            self.unit.status = ops.BlockedStatus(exc.msg)
            return

        pebble_service = pebble.PebbleService(state)

        # Gate 1: container must be connected.
        container = self.unit.get_container(state.jenkins_agent_service_name)
        if not container.can_connect():
            logger.info("Container not yet ready. Deferring.")
            event.defer()
            return

        # Determine the credentials source: config takes priority over relation.
        credentials, source = self._resolve_credentials(state, container)
        if credentials is None and source == "blocked":
            return  # Status already set
        if credentials is None and source == "waiting":
            event.defer()
            return

        assert credentials is not None  # nosec  # noqa: S101

        # Gate 2: if agent is already running with correct credentials, nothing to do.
        if container.exists(
            str(server.AGENT_READY_PATH)
        ) and not pebble_service.credentials_changed(
            container=container,
            server_url=credentials.address,
            agent_token=credentials.secret,
        ):
            logger.info("Agent registered with current credentials. No restart needed.")
            self.unit.status = ops.ActiveStatus()
            return

        # Gate 3: verify server is reachable before making changes.
        if not server.server_is_ready(credentials.address):
            logger.info("Server at %s not yet reachable. Deferring.", credentials.address)
            self.unit.status = ops.WaitingStatus("Waiting for Jenkins server to become ready.")
            event.defer()
            return

        # Gate 4 (config mode only): validate agent credentials against server.
        if source == "config":
            self._reconcile_from_config(state, pebble_service, container, event)
            return

        # Apply: stop existing agent (if running) and start with new credentials.
        if container.exists(str(server.AGENT_READY_PATH)):
            logger.info("Credentials changed. Stopping current agent.")
            pebble_service.stop_agent(container=container)

        self._start_agent(
            state, pebble_service, container, credentials, state.agent_meta.name, event
        )

    def _resolve_credentials(
        self, state: State, container: ops.Container
    ) -> typing.Tuple[typing.Optional[server.Credentials], str]:
        """Determine the credential source.

        Args:
            state: Current charm state.
            container: The workload container.

        Returns:
            Tuple of (credentials or None, source label). Source is one of:
            "config", "relation", "blocked", "waiting".
        """
        if state.jenkins_config:
            # Config mode — credentials come from juju config.
            # Secret is not used in config mode; server_url is sufficient.
            config_secret = ""  # nosec: B105
            return (
                server.Credentials(
                    address=state.jenkins_config.server_url,
                    secret=config_secret,
                ),
                "config",
            )

        if not self.model.get_relation(AGENT_RELATION):
            self.unit.status = ops.BlockedStatus("Waiting for config/relation.")
            return None, "blocked"

        if not state.agent_relation_credentials:
            self.unit.status = ops.WaitingStatus("Waiting for complete relation data.")
            logger.info("Waiting for complete relation data.")
            return None, "waiting"

        return state.agent_relation_credentials, "relation"

    def _reconcile_from_config(
        self,
        state: State,
        pebble_service: pebble.PebbleService,
        container: ops.Container,
        event: ops.EventBase,
    ) -> None:
        """Handle the config-based registration path.

        Args:
            state: Current charm state.
            pebble_service: The pebble service manager.
            container: The workload container.
            event: The triggering event (for deferral).
        """
        assert state.jenkins_config is not None  # nosec  # noqa: S101

        # If there's also an agent relation, config takes priority — block.
        if self.model.get_relation(AGENT_RELATION):
            self.unit.status = ops.BlockedStatus("Please remove and re-relate agent relation.")
            return

        self.unit.status = ops.MaintenanceStatus("Downloading Jenkins agent executable.")
        try:
            server.download_jenkins_agent(
                server_url=state.jenkins_config.server_url,
                container=container,
            )
        except server.AgentJarDownloadError:
            logger.warning("Failed to download agent.jar from config URL. Deferring.")
            self.unit.status = ops.WaitingStatus("Waiting for Jenkins server.")
            event.defer()
            return

        valid_agent_token = server.find_valid_credentials(
            agent_name_token_pairs=state.jenkins_config.agent_name_token_pairs,
            server_url=state.jenkins_config.server_url,
            container=container,
        )
        if not valid_agent_token:
            logger.error("No valid agent-token pair found.")
            self.unit.status = ops.BlockedStatus("Additional valid agent-token pairs required.")
            return

        self.unit.status = ops.MaintenanceStatus("Starting agent pebble service.")
        pebble_service.reconcile(
            server_url=state.jenkins_config.server_url,
            agent_token_pair=valid_agent_token,
            container=container,
        )
        self.unit.status = ops.ActiveStatus()

    def _start_agent(
        self,
        state: State,
        pebble_service: pebble.PebbleService,
        container: ops.Container,
        credentials: server.Credentials,
        agent_name: str,
        event: ops.EventBase,
    ) -> None:
        """Download agent.jar and start the pebble service.

        Args:
            state: Current charm state.
            pebble_service: The pebble service manager.
            container: The workload container.
            credentials: Server credentials for registration.
            agent_name: The agent name to register as.
            event: The triggering event (for deferral on failure).
        """
        self.unit.status = ops.MaintenanceStatus("Downloading Jenkins agent executable.")
        try:
            server.download_jenkins_agent(server_url=credentials.address, container=container)
        except server.AgentJarDownloadError:
            logger.warning("Failed to download agent.jar. Server may not be ready. Deferring.")
            self.unit.status = ops.WaitingStatus("Waiting for Jenkins server.")
            event.defer()
            return

        self.unit.status = ops.MaintenanceStatus("Starting agent pebble service.")
        pebble_service.reconcile(
            server_url=credentials.address,
            agent_token_pair=(agent_name, credentials.secret),
            container=container,
        )
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: no cover
    main(JenkinsAgentCharm)
