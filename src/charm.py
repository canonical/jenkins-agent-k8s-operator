#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm k8s jenkins agent."""

import logging
import typing

import ops
from ops.main import main

import agent
import pebble
import server
from state import AGENT_RELATION, SLAVE_RELATION, InvalidStateError, State

logger = logging.getLogger()


class JenkinsAgentCharm(ops.CharmBase):
    """Charm Jenkins k8s agent."""

    def __init__(self, *args: typing.Any):
        """Initialize the charm and register event handlers.

        Args:
            args: Arguments to initialize the charm base.
        """
        super().__init__(*args)
        try:
            self.state = State.from_charm(self)
        except InvalidStateError as exc:
            self.unit.status = ops.BlockedStatus(exc.msg)
            return

        self.pebble_service = pebble.PebbleService(self.state)
        self.agent_observer = agent.Observer(self, self.state, self.pebble_service)

        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

    def _register_via_config(
        self, event: typing.Union[ops.ConfigChangedEvent, ops.UpgradeCharmEvent]
    ) -> None:
        """Register the agent to server from configuration values.

        Args:
            event: The event fired on config changed or upgrade charm.
        """
        container = self.unit.get_container(self.state.jenkins_agent_service_name)
        if not container.can_connect():
            logger.warning("Jenkins agent container not yet ready. Deferring.")
            event.defer()
            return

        if (
            not self.state.jenkins_config
            and not self.model.get_relation(SLAVE_RELATION)
            and not self.model.get_relation(AGENT_RELATION)
        ):
            self.model.unit.status = ops.BlockedStatus("Waiting for config/relation.")
            return

        if not self.state.jenkins_config:
            if self.model.get_relation(SLAVE_RELATION):
                self.model.unit.status = ops.BlockedStatus(
                    "Please remove and re-relate slave relation."
                )
                return
            # Support fallback relation to AGENT_RELATION.
            self.model.unit.status = ops.BlockedStatus(
                "Please remove and re-relate agent relation."
            )
            return

        try:
            server.download_jenkins_agent(
                server_url=self.state.jenkins_config.server_url,
                container=container,
            )
        except server.AgentJarDownloadError as exc:
            logger.error("Failed to download Agent JAR executable, %s", exc)
            self.model.unit.status = ops.ErrorStatus("Failed to download Agent JAR executable.")
            return

        valid_agent_token = server.find_valid_credentials(
            agent_name_token_pairs=self.state.jenkins_config.agent_name_token_pairs,
            server_url=self.state.jenkins_config.server_url,
            container=container,
        )
        if not valid_agent_token:
            logger.error("No valid agent-token pair found.")
            self.model.unit.status = ops.BlockedStatus(
                "Additional valid agent-token pairs required."
            )
            return

        self.model.unit.status = ops.MaintenanceStatus("Starting agent pebble service.")
        self.pebble_service.reconcile(
            server_url=self.state.jenkins_config.server_url,
            agent_token_pair=valid_agent_token,
            container=container,
        )
        self.model.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        """Handle config changed event.

        Args:
            event: The event fired on configuration change.
        """
        self._register_via_config(event)

    def _on_upgrade_charm(self, event: ops.UpgradeCharmEvent) -> None:
        """Handle upgrade charm event.

        Args:
            event: The event fired on upgrade charm.
        """
        self._register_via_config(event)


if __name__ == "__main__":  # pragma: no cover
    main(JenkinsAgentCharm)
