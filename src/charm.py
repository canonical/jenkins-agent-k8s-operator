#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import logging
import os
import yaml

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus


logger = logging.getLogger()


class JenkinsAgentCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_config_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_config_changed)
        self.framework.observe(self.on.slave_relation_joined, self.on_agent_relation_joined)
        self.framework.observe(self.on.slave_relation_changed, self.on_agent_relation_changed)

        self._stored.set_default(spec=None, jenkins_url=None, agent_tokens=None, agents=None)
        self.service_name = "jenkins-agent"

    def _get_pebble_config(self, event):
        """Generate our pebble config."""
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

    def _on_config_changed(self, event):
        """Handle config-changed event."""

        is_valid = self._is_valid_config()
        if not is_valid:
            # Charm will be in blocked status.
            return

        pebble_config = self._get_pebble_config(event)
        container = self.unit.get_container(self.service_name)

        services = container.get_plan().to_dict().get("services", [])
        if services != pebble_config["services"]:
            logger.debug("About to add_layer with pebble_config:\n{}".format(yaml.dump(pebble_config)))
            container.add_layer(self.service_name, pebble_config, combine=True)

            self._restart_service(self.service_name, container)
        else:
            logger.debug("Pebble config unchanged")

        self.unit.status = ActiveStatus()

    def _restart_service(self, service_name, container):
        """Restart a service"""
        if container.get_service(service_name).is_running():
            container.stop(service_name)
        container.start(service_name)

    def _missing_charm_settings(self):
        """Check configuration setting dependencies

        Return a list of missing settings; otherwise return an empty list."""
        config = self.model.config
        if self._stored.agent_tokens:
            required_settings = ("image",)
        else:
            required_settings = ("image", "jenkins_url", "jenkins_agent_name", "jenkins_agent_token")

        missing = [setting for setting in required_settings if not config[setting]]

        return sorted(missing)

    def _is_valid_config(self):
        """Validate required configuration.

        When not configuring the agent through relations
        'jenkins_url', 'jenkins_agent_name' and 'jenkins_agent_token'
        are required."""
        is_valid = True

        missing = self._missing_charm_settings()
        if missing:
            message = "Missing required config: {}".format(" ".join(missing))
            logger.info(message)
            self.model.unit.status = BlockedStatus(message)
            is_valid = False

        return is_valid

    def on_agent_relation_joined(self, event):
        """Set relation data for the unit once an agent has connected."""
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

    def on_agent_relation_changed(self, event):
        """Populate local configuration with data from relation."""
        logger.info("Jenkins relation changed")
        try:
            self._stored.jenkins_url = event.relation.data[event.unit]['url']
        except KeyError:
            pass

        try:
            self._stored.agent_tokens = self._stored.agent_tokens or []
            self._stored.agent_tokens.append(event.relation.data[event.unit]['secret'])
            self._gen_agent_name(store=True)
        except KeyError:
            pass

        print("alejdg")
        print(self.valid_relation_data(event))
        if self.valid_relation_data(event):
            print("it's valid")
            self._on_config_changed(event)

    def valid_relation_data(self, event):
        """Configure the agent through data from relation."""
        logger.info("Setting up jenkins via agent relation")
        self.model.unit.status = MaintenanceStatus("Configuring jenkins agent")

        if self.model.config.get("jenkins_url"):
            logger.info("Config option 'jenkins_url' is set. Can't use agent relation.")
            self.model.unit.status = ActiveStatus()
            return False

        if self._stored.jenkins_url is None:
            logger.info("Jenkins hasn't exported its URL yet. Skipping setup for now.")
            self.model.unit.status = ActiveStatus()
            return False

        if self._stored.agent_tokens is None:
            logger.info("Jenkins hasn't exported the agent secret yet. Skipping setup for now.")
            self.model.unit.status = ActiveStatus()
            return False
        return True

    def _gen_agent_name(self, store=False):
        """Generate the agent name or get the one already in use."""
        agent_name = ""
        if self._stored.agents:
            name, number = self._stored.agents[-1].rsplit('-', 1)
            agent_name = "{}-{}".format(name, int(number) + 1)
            if store:
                self._stored.agents.append(agent_name)
        else:
            agent_name = self.unit.name.replace('/', '-')
            if store:
                self._stored.agents = [agent_name]
        return agent_name

    def _get_env_config(self):
        env_config = {}
        if self._stored.jenkins_url:
            env_config["JENKINS_URL"] = self._stored.jenkins_url
        else:
            env_config["JENKINS_URL"] = self.config["jenkins_url"]

        if self._stored.agent_tokens and self._stored.agents:
            env_config["JENKINS_AGENTS"] = ":".join(self._stored.agents)
            env_config["JENKINS_TOKENS"] = ":".join(self._stored.agent_tokens)
        else:
            env_config["JENKINS_AGENTS"] = self.config["jenkins_agent_name"]
            env_config["JENKINS_TOKENS"] = self.config["jenkins_agent_token"]

        return env_config


if __name__ == '__main__':  # pragma: no cover
    # use_juju_for_storage is a workaround for states not persisting through upgrades:
    # https://github.com/canonical/operator/issues/506
    main(JenkinsAgentCharm, use_juju_for_storage=True)
