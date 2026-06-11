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

    Uses a reconciliation pattern: all events funnel to _on_reconcile() which
    computes the desired state from current reality and applies it idempotently.
    """

    def __init__(self, *args: typing.Any):
        """Initialize the charm and register event handlers.

        Args:
            args: Arguments to initialize the charm base.
        """
        super().__init__(*args)

        # All events converge on the same reconcile handler.
        for event in (
            self.on.config_changed,
            self.on.upgrade_charm,
            self.on.jenkins_agent_k8s_pebble_ready,
            self.on[AGENT_RELATION].relation_joined,
            self.on[AGENT_RELATION].relation_changed,
            self.on[AGENT_RELATION].relation_departed,
        ):
            self.framework.observe(event, self._on_reconcile)

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
            logger.info("Container not yet ready. Wait for the next event.")
            return

        # Determine the credentials source: config takes priority over relation.
        credentials, source = self._resolve_credentials(state, container)

        if credentials is None:
            self._handle_no_credentials(pebble_service, container)
            return

        # Guard: if both config and relation are present, block (ambiguous state).
        if source == "config" and self.model.get_relation(AGENT_RELATION):
            self.unit.status = ops.BlockedStatus("Please remove either configuration or agent relation.")
            return

        # Ensure relation databag is populated (idempotent, covers relation-joined).
        if source == "relation":
            self._ensure_databag_published(state)

        # Gate 2: if agent is already running with correct credentials, nothing to do.
        # Config mode skipped: credentials.secret is empty placeholder and token resolution
        # happens inside _reconcile_from_config(), so up-to-date check is invalid here.
        if source != "config" and self._agent_up_to_date(pebble_service, container, credentials):
            self.unit.status = ops.ActiveStatus()
            return

        # Gate 3: verify server is reachable before making changes.
        if not server.server_is_ready(credentials.address):
            logger.info("Server at %s not yet reachable.", credentials.address)
            raise RuntimeError(f"Server at {credentials.address} not reachable.")

        # Gate 4 (config mode only): validate agent credentials against server.
        if source == "config":
            self._reconcile_from_config(state, pebble_service, container)
            return

        # Apply: stop existing agent (if running) and start with new credentials.
        if container.exists(str(server.AGENT_READY_PATH)):
            logger.info("Credentials changed. Stopping current agent.")
            pebble_service.stop_agent(container=container)

        self._start_agent(pebble_service, container, credentials, state.agent_meta.name)

    def _agent_up_to_date(
        self,
        pebble_service: pebble.PebbleService,
        container: ops.Container,
        credentials: server.Credentials,
    ) -> bool:
        """Check whether the agent is already running with the given credentials.

        Args:
            pebble_service: The pebble service manager.
            container: The workload container.
            credentials: The desired credentials to compare against.

        Returns:
            True if the agent is running and credentials match (no restart needed).
        """
        if not container.exists(str(server.AGENT_READY_PATH)):
            return False
        if pebble_service.credentials_changed(
            container=container,
            server_url=credentials.address,
            agent_token=credentials.secret,
        ):
            return False
        logger.info("Agent registered with current credentials. No restart needed.")
        return True

    def _handle_no_credentials(
        self,
        pebble_service: pebble.PebbleService,
        container: ops.Container
    ) -> None:
        """Handle the case where no valid credentials are available.

        Ensures any running agent is stopped.

        Args:
            pebble_service: The pebble service manager.
            container: The workload container.
        """
        if container.exists(str(server.AGENT_READY_PATH)):
            pebble_service.stop_agent(container=container)

    def _ensure_databag_published(self, state: State) -> None:
        """Publish agent metadata to the relation databag if not already present.

        This is idempotent — only writes when the databag content differs from
        the expected metadata, preventing unnecessary relation-changed events.

        Args:
            state: Current charm state.
        """
        relation = self.model.get_relation(AGENT_RELATION)
        if relation is None:
            # This should not happen as caller ensures source == "relation"
            logger.error("Relation %s missing in _ensure_databag_published", AGENT_RELATION)
            raise RuntimeError(f"Relation {AGENT_RELATION} not found when ensuring databag published.")
        expected = state.agent_meta.get_jenkins_agent_v0_interface_dict()
        current = dict(relation.data[self.unit])
        if current != expected:
            logger.info("Syncing relation databag to match expected metadata.")
            relation.data[self.unit].update(expected)
        else:
            logger.debug("Relation databag already up to date.")

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
    ) -> None:
        """Handle the config-based registration path.

        Args:
            state: Current charm state.
            pebble_service: The pebble service manager.
            container: The workload container.
        """
        if state.jenkins_config is None:
            logger.error("Jenkins config missing in config reconciliation path.")
            self.unit.status = ops.BlockedStatus("Internal error: config state missing.")
            return

        self.unit.status = ops.MaintenanceStatus("Downloading Jenkins agent executable.")
        try:
            server.download_jenkins_agent(
                server_url=state.jenkins_config.server_url,
                container=container,
            )
        except server.AgentJarDownloadError:
            logger.error("Failed to download agent.jar from config URL. Server may not be ready.")
            raise

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
        pebble_service: pebble.PebbleService,
        container: ops.Container,
        credentials: server.Credentials,
        agent_name: str,
    ) -> None:
        """Download agent.jar and start the pebble service.

        Args:
            state: Current charm state.
            pebble_service: The pebble service manager.
            container: The workload container.
            credentials: Server credentials for registration.
            agent_name: The agent name to register as.
        """
        self.unit.status = ops.MaintenanceStatus("Downloading Jenkins agent executable.")
        try:
            server.download_jenkins_agent(server_url=credentials.address, container=container)
        except server.AgentJarDownloadError:
            logger.error("Failed to download agent.jar. Server may not be ready.")
            raise

        self.unit.status = ops.MaintenanceStatus("Starting agent pebble service.")
        pebble_service.reconcile(
            server_url=credentials.address,
            agent_token_pair=(agent_name, credentials.secret),
            container=container,
        )
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: no cover
    main(JenkinsAgentCharm)
