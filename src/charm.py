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

        self.pebble_service = pebble.PebbleService(self, self.state)
        self.agent_observer = agent.Observer(self, self.state, self.pebble_service)

        self.framework.observe(
            self.on.jenkins_k8s_agent_pebble_ready, self._register_agent_from_config
        )
        self.framework.observe(self.on.config_changed, self._register_agent_from_config)
        self.framework.observe(self.on.upgrade_charm, self._register_agent_from_config)

    @property
    def _jenkins_agent_container(self) -> ops.Container:
        """The Jenkins workload container."""
        return self.unit.get_container(self.state.jenkins_agent_service_name)

    def _register_agent_from_config(self, event: ops.HookEvent) -> None:
        """Handle pebble ready event.

        Args:
            event: The base hook event.
        """
        container = self._jenkins_agent_container
        if not container or not container.can_connect():
            logger.warning("Jenkins agent container not yet ready. Deferring.")
            event.defer()
            return

        if (
            not self.state.jenkins_config
            and not self.model.get_relation(AGENT_RELATION)
            and not self.model.get_relation(SLAVE_RELATION)
        ):
            self.model.unit.status = ops.BlockedStatus("Waiting for config/relation.")
            return

        if not self.state.jenkins_config:
            logger.info("Using Jenkins from relation.")
            return

        try:
            server.download_jenkins_agent(
                server_url=self.state.jenkins_config.server_url,
                connectable_container=container,
            )
        except server.AgentJarDownloadError as exc:
            logger.error("Failed to download Agent JAR executable, %s", exc)
            self.model.unit.status = ops.BlockedStatus("Failed to download Agent JAR executable.")
            return

        valid_agent_token: typing.Optional[typing.Tuple[str, str]] = None
        for agent_name, agent_token in zip(
            self.state.jenkins_config.agent_names, self.state.jenkins_config.agent_tokens
        ):
            logger.warning("[%s]Validating %s", self.state.agent_meta.name, agent_name)
            if not server.validate_credentials(
                agent_name=agent_name,
                credentials=server.Credentials(
                    address=self.state.jenkins_config.server_url, secret=agent_token
                ),
                connectable_container=container,
            ):
                logger.error(
                    "[%s]agent %s validation failed.", self.state.agent_meta.name, agent_name
                )
                continue
            valid_agent_token = (agent_name, agent_token)

        if not valid_agent_token:
            logger.error("No valid agent-token pair found.")
            self.model.unit.status = ops.BlockedStatus("Exhausted valid agent-token pairs.")
            return

        self.pebble_service.reconcile(
            server_url=self.state.jenkins_config.server_url, agent_token_pairs=(valid_agent_token,)
        )


if __name__ == "__main__":  # pragma: no cover
    main(JenkinsAgentCharm)
