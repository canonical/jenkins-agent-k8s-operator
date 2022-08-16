#!/usr/bin/env python3

# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import logging
import os
import typing

import yaml
from ops import charm, framework, main, model

logger = logging.getLogger()


class JenkinsAgentCharStoredState(framework.StoredState):
    """Defines valid attributes of the stored state for the Jenkins Agent."""

    relation_configured: bool | None
    jenkins_url: str | None
    agents: list[str] | None
    agent_tokens: list[str] | None


class JenkinsAgentEnvConfig(typing.TypedDict):
    """The envornment configuration for the jenkins agent."""

    JENKINS_AGENTS: str
    JENKINS_TOKENS: str
    JENKINS_URL: str


class JenkinsAgentCharm(charm.CharmBase):
    _stored = JenkinsAgentCharStoredState()
    service_name = "jenkins-agent"

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_config_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_config_changed)
        self.framework.observe(self.on.slave_relation_joined, self._on_agent_relation_joined)
        self.framework.observe(self.on.slave_relation_changed, self._on_agent_relation_changed)

        self._stored.set_default(
            relation_configured=False, jenkins_url=None, agents=None, agent_tokens=None
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

    def _on_config_changed(self, event: charm.ConfigChangedEvent) -> None:
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
            self.unit.status = model.BlockedStatus(message)
            return

        # Add any newly required or update any changed services
        pebble_config = self._get_pebble_config()
        container = self.unit.get_container(self.service_name)
        services = container.get_plan().to_dict().get("services", {})
        if services != pebble_config["services"]:
            logger.debug(f"About to add_layer with pebble_config:\n{yaml.dump(pebble_config)}")
            container.add_layer(self.service_name, pebble_config, combine=True)
            container.restart(self.service_name)
        else:
            logger.debug("Pebble config unchanged")

        self.unit.status = model.ActiveStatus()

    def _is_valid_config(self) -> tuple[True, None] | tuple[False, str]:
        """Validate required configuration.

        When not configuring the agent through relations (as indicated by relation_configured
        stored state), 'jenkins_url', 'jenkins_agent_name' and 'jenkins_agent_token' are required.

        Returns:
            Whether the configuration is valid, including a reason if it is not.
        """
        # Check for agent tokens
        if self._stored.relation_configured:
            return True, None

        # Retrieve required and non-empty configuration options
        required_options = {"jenkins_url", "jenkins_agent_name", "jenkins_agent_token"}
        non_empty_options = {option for option in required_options if self.model.config[option]}

        if required_options.issubset(non_empty_options):
            return True, None

        return (
            False,
            f"Missing required configuration: {' '.join(sorted(required_options - non_empty_options))}",
        )

    def _on_agent_relation_joined(self, event: charm.RelationJoinedEvent) -> None:
        """Set relation data for the unit once an agent has connected.

        Args:
            event: information about the relation joined event.
        """
        logger.info("Jenkins relation joined")
        num_executors = os.cpu_count()
        config_labels = self.model.config.get('jenkins_agent_labels')
        agent_name = self._gen_agent_name()

        if config_labels:
            labels = config_labels
        else:
            labels = os.uname().machine

        event.relation.data[self.model.unit]["executors"] = str(num_executors)
        event.relation.data[self.model.unit]["labels"] = labels
        event.relation.data[self.model.unit]["slavehost"] = agent_name

    def _on_agent_relation_changed(self, event: charm.RelationChangedEvent):
        """Populate local configuration with data from relation."""
        logger.info("Jenkins relation changed")
        agent_name = self._gen_agent_name()
        self._stored.agents = [agent_name]
        self._stored.agent_tokens = self._stored.agent_tokens or []

        # Check event data
        try:
            relation_jenkins_url = event.relation.data[event.unit]['url']
        except KeyError:
            logger.warning(
                f"Expected 'url' key for {event.unit} unit in relation data. "
                "Skipping setup for now."
            )
            self.model.unit.status = model.ActiveStatus()
            return
        try:
            relation_secret = event.relation.data[event.unit]['secret']
        except KeyError:
            logger.warning(
                f"Expected 'secret' key for {event.unit} unit in relation data. "
                "Skipping setup for now."
            )
            self.model.unit.status = model.ActiveStatus()
            return
        self._stored.jenkins_url = relation_jenkins_url
        self._stored.agent_tokens.append(relation_secret)
        self._stored.relation_configured = True

        # Check whether jenkins_url has been set
        if self.model.config.get("jenkins_url"):
            logger.warning("Config option 'jenkins_url' is set, ignoring and using agent relation.")

        logger.info("Setting up jenkins via agent relation")
        self.model.unit.status = model.MaintenanceStatus("Configuring jenkins agent")
        self.on.config_changed.emit()

    def _gen_agent_name(self) -> str:
        """Generate the agent name or get the one already in use.

        Returns:
            The agent name.
        """
        agent_name = ""
        if self._stored.agents:
            name, number = self._stored.agents[-1].rsplit('-', 1)
            agent_name = f"{name}-{int(number) + 1}"
        else:
            agent_name = self.unit.name.replace('/', '-')

        return agent_name

    def _get_env_config(self) -> JenkinsAgentEnvConfig:
        """Retrieve the environment configuration.

        Reads the jenkis url, agents and tokens either from the configuration or as set by a
        relation to jenkins with the relation data preferred over the configuration.

        Returns:
            A dictionary with the environment variables to be set for the jenkins agent.
        """
        if self._stored.relation_configured:
            return {
                "JENKINS_URL": self._stored.jenkins_url,
                "JENKINS_AGENTS": ":".join(self._stored.agents),
                "JENKINS_TOKENS": ":".join(self._stored.agent_tokens),
            }
        return {
            "JENKINS_URL": self.config["jenkins_url"],
            "JENKINS_AGENTS": self.config["jenkins_agent_name"],
            "JENKINS_TOKENS": self.config["jenkins_agent_token"],
        }


if __name__ == '__main__':  # pragma: no cover
    # use_juju_for_storage is a workaround for states not persisting through upgrades:
    # https://github.com/canonical/operator/issues/506
    main.main(JenkinsAgentCharm, use_juju_for_storage=True)
