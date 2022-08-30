#!/usr/bin/env python3

# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

"""Charm for Jenkins Agent on kubernetes."""

import logging
import os
import typing
import uuid

import yaml
from ops.charm import (
    CharmBase,
    ConfigChangedEvent,
    RelationChangedEvent,
    RelationJoinedEvent,
)
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

logger = logging.getLogger()


class JenkinsAgentCharmStoredState(StoredState):
    """Defines valid attributes of the stored state for the Jenkins Agent."""

    # Disabling since class is used to add type information to the stored state.
    # pylint: disable=too-few-public-methods

    relation_configured: bool | None
    jenkins_url: str | None
    relation_agent_name: str
    relation_agent_token: str | None


class JenkinsAgentEnvConfig(typing.TypedDict):
    """The environment configuration for the jenkins agent."""

    JENKINS_AGENTS: str
    JENKINS_TOKENS: str
    JENKINS_URL: str


class JenkinsAgentCharm(CharmBase):
    """Charm for Jenkins Agent on kubernetes."""

    _stored = JenkinsAgentCharmStoredState()
    service_name = "jenkins-agent"

    def __init__(self, *args) -> None:
        """Constructor."""
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_config_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_config_changed)
        self.framework.observe(self.on.slave_relation_joined, self._on_agent_relation_joined)
        self.framework.observe(self.on.slave_relation_changed, self._on_agent_relation_changed)

        self._stored.set_default(
            relation_configured=False,
            jenkins_url=None,
            relation_agent_name=f"{self.unit.name.replace('/', '-')}-{uuid.uuid4()}",
            relation_agent_token=None,
        )

    def _get_pebble_config(self) -> dict:
        """Generate the pebble config for the charm.

        Returns:
            The pebble configuration for the charm.
        """
        env_config = self._get_env_config()
        pebble_config = {
            "summary": "jenkins agent layer",
            "description": "Jenkins Agent layer",
            "services": {
                "jenkins-agent": {
                    "override": "replace",
                    "summary": "Jenkins Agent service",
                    "command": "/entrypoint.sh",
                    "startup": "enabled",
                    "environment": env_config,
                }
            },
        }
        return pebble_config

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Handle config-changed event.

        Args:
            event: The information about the event.
        """
        # Check for container connectivity
        if not self.unit.get_container(self.service_name).can_connect():
            event.defer()
            return

        # Check whether configuration is valid
        config_valid, message = self._is_valid_config()
        if not config_valid:
            logger.info(message)
            self.unit.status = BlockedStatus(message)
            return

        # Add any newly required or update any changed services
        pebble_config = self._get_pebble_config()
        container = self.unit.get_container(self.service_name)
        services = container.get_plan().to_dict().get("services", {})
        if services != pebble_config["services"]:
            logger.debug("About to add_layer with pebble_config:\n%s", yaml.dump(pebble_config))
            self.unit.status = MaintenanceStatus(f"Adding {container.name} layer to pebble")
            container.add_layer(self.service_name, pebble_config, combine=True)
            self.unit.status = MaintenanceStatus(f"Starting {container.name} container")
            container.pebble.replan_services()
        else:
            logger.debug("Pebble config unchanged")

        self.unit.status = ActiveStatus()

    def _is_valid_config(self) -> tuple[bool, str]:
        """Validate required configuration.

        When not configuring the agent through relations (as indicated by relation_configured
        stored state), 'jenkins_url', 'jenkins_agent_name' and 'jenkins_agent_token' are required.

        Returns:
            Whether the configuration is valid, including a reason if it is not.
        """
        # Check for agent tokens
        if self._stored.relation_configured:
            return True, ""

        # Retrieve required and non-empty configuration options
        required_options = {"jenkins_url", "jenkins_agent_name", "jenkins_agent_token"}
        non_empty_options = {option for option in required_options if self.model.config[option]}

        if required_options.issubset(non_empty_options):
            return True, ""

        return (
            False,
            "Missing required configuration: "
            f"{' '.join(sorted(required_options - non_empty_options))}",
        )

    def _on_agent_relation_joined(self, event: RelationJoinedEvent) -> None:
        """Set relation data for the unit once an agent has connected.

        Args:
            event: information about the relation joined event.
        """
        logger.info("Jenkins relation joined")
        num_executors = os.cpu_count()
        config_labels = self.model.config.get("jenkins_agent_labels")

        if config_labels:
            labels = config_labels
        else:
            labels = os.uname().machine

        event.relation.data[self.model.unit]["executors"] = str(num_executors)
        event.relation.data[self.model.unit]["labels"] = labels
        event.relation.data[self.model.unit]["slavehost"] = self._stored.relation_agent_name

    def _on_agent_relation_changed(self, event: RelationChangedEvent) -> None:
        """Populate local configuration with data from relation.

        Args:
            event: information about the relation changed event.
        """
        logger.info("Jenkins relation changed")

        # Check event data
        try:
            relation_jenkins_url = event.relation.data[event.unit]["url"]
        except KeyError:
            logger.warning(
                "Expected 'url' key for %s unit in relation data. Skipping setup for now.",
                event.unit,
            )
            self.model.unit.status = ActiveStatus()
            return
        try:
            relation_secret = event.relation.data[event.unit]["secret"]
        except KeyError:
            logger.warning(
                "Expected 'secret' key for %s unit in relation data. Skipping setup for now.",
                event.unit,
            )
            self.model.unit.status = ActiveStatus()
            return
        self._stored.jenkins_url = relation_jenkins_url
        self._stored.relation_agent_token = relation_secret
        self._stored.relation_configured = True

        # Check whether jenkins_url has been set
        if self.model.config.get("jenkins_url"):
            logger.warning(
                "Config option 'jenkins_url' is set, ignoring and using agent relation."
            )

        logger.info("Setting up jenkins via agent relation")
        self.model.unit.status = MaintenanceStatus("Configuring jenkins agent")
        self.on.config_changed.emit()

    def _get_env_config(self) -> JenkinsAgentEnvConfig:
        """Retrieve the environment configuration.

        Reads the jenkis url, agents and tokens either from the configuration or as set by a
        relation to jenkins with the relation data preferred over the configuration.

        Returns:
            A dictionary with the environment variables to be set for the jenkins agent.
        """
        if self._stored.relation_configured:
            return {
                "JENKINS_URL": self._stored.jenkins_url or "",
                "JENKINS_AGENTS": self._stored.relation_agent_name,
                "JENKINS_TOKENS": self._stored.relation_agent_token,
            }
        return {
            "JENKINS_URL": self.config["jenkins_url"],
            "JENKINS_AGENTS": self.config["jenkins_agent_name"],
            "JENKINS_TOKENS": self.config["jenkins_agent_token"],
        }


if __name__ == "__main__":  # pragma: no cover
    # use_juju_for_storage is a workaround for states not persisting through upgrades:
    # https://github.com/canonical/operator/issues/506
    main(JenkinsAgentCharm, use_juju_for_storage=True)
