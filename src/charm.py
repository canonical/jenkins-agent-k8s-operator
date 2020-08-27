#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import io
import logging
import os
import pprint

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus


logger = logging.getLogger()


class JenkinsAgentCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.framework.observe(self.on.start, self.configure_pod)
        self.framework.observe(self.on.config_changed, self.configure_pod)
        self.framework.observe(self.on.upgrade_charm, self.configure_pod)
        self.framework.observe(self.on.slave_relation_joined, self.on_agent_relation_joined)
        self.framework.observe(self.on.slave_relation_changed, self.on_agent_relation_changed)

        self._stored.set_default(_spec=None, jenkins_url=None, agent_tokens=None, agents=None)

    def generate_pod_config(self, config, secured=True):
        """Kubernetes pod config generator.

        generate_pod_config generates Kubernetes deployment config.
        If the secured keyword is set then it will return a sanitised copy
        without exposing secrets.
        """
        pod_config = {}

        if self._stored.jenkins_url:
            pod_config["JENKINS_URL"] = self._stored.jenkins_url
        else:
            pod_config["JENKINS_URL"] = config["jenkins_master_url"]

        if secured:
            return pod_config

        if self._stored.agent_tokens and self._stored.agents:
            pod_config["JENKINS_AGENTS"] = ":".join(self._stored.agents)
            pod_config["JENKINS_TOKENS"] = ":".join(self._stored.agent_tokens)
        else:
            pod_config["JENKINS_AGENTS"] = config["jenkins_agent_name"]
            pod_config["JENKINS_TOKENS"] = config["jenkins_agent_token"]

        return pod_config

    def configure_pod(self, event):
        """Assemble the pod spec and apply it, if possible."""
        is_valid = self.is_valid_config()
        if not is_valid:
            return

        spec = self.make_pod_spec()
        if spec != self._stored._spec:
            self._stored._spec = spec
            # only the leader can set_spec()
            if self.model.unit.is_leader():
                spec = self.make_pod_spec()

                logger.info("Configuring pod")
                self.model.unit.status = MaintenanceStatus("Configuring pod")
                self.model.pod.set_spec(spec)

                logger.info("Pod configured")
                self.model.unit.status = MaintenanceStatus("Pod configured")
            else:
                logger.info("Spec changes ignored by non-leader")
        else:
            logger.info("Pod spec unchanged")

        self._stored.is_started = True
        self.model.unit.status = ActiveStatus()

    def make_pod_spec(self):
        """Prepare and return a pod spec."""
        config = self.model.config

        full_pod_config = self.generate_pod_config(config, secured=False)
        secure_pod_config = self.generate_pod_config(config, secured=True)

        spec = {
            "containers": [
                {
                    "config": secure_pod_config,
                    "imageDetails": {"imagePath": config["image"]},
                    "name": self.app.name,
                    "readinessProbe": {"exec": {"command": ["/bin/cat", "/var/lib/jenkins/agents/.ready"]}},
                }
            ],
        }

        out = io.StringIO()
        pprint.pprint(spec, out)
        logger.info("This is the Kubernetes Pod spec config (sans secrets) <<EOM\n{}\nEOM".format(out.getvalue()))

        secure_pod_config.update(full_pod_config)
        return spec

    def is_valid_config(self):
        """Validate required configuration.

        When not configuring the agent through relations
        'jenkins_master_url', 'jenkins_agent_name' and 'jenkins_agent_token'
        are required."""
        is_valid = True

        config = self.model.config
        if self._stored.agent_tokens:
            want = ("image",)
        else:
            want = ("image", "jenkins_master_url", "jenkins_agent_name", "jenkins_agent_token")
        missing = [k for k in want if config[k].rstrip() == ""]
        if missing:
            message = "Missing required config: {}".format(" ".join(missing))
            logger.info(message)
            self.model.unit.status = BlockedStatus(message)
            is_valid = False

        return is_valid

    def on_agent_relation_joined(self, event):
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
        """Populate local configuration with data from relation"""
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

        self.configure_through_relation(event)

    def configure_through_relation(self, event):
        logger.info("Setting up jenkins via agent relation")
        self.model.unit.status = MaintenanceStatus("Configuring jenkins agent")

        if self.model.config.get("jenkins_master_url"):
            logger.info("Config option 'jenkins_master_url' is set. Can't use agent relation.")
            self.model.unit.status = ActiveStatus()
            return

        if self._stored.jenkins_url is None:
            logger.info("Jenkins hasn't exported its url yet. Skipping setup for now.")
            self.model.unit.status = ActiveStatus()
            return

        if self._stored.agent_tokens is None:
            logger.info("Jenkins hasn't exported the agent secret yet. Skipping setup for now.")
            self.model.unit.status = ActiveStatus()
            return

        self.configure_pod(event)

    def _gen_agent_name(self, store=False):
        agent_name = ""
        if self._stored.agents:
            name, number = self._stored.agents[-1].rsplit('-', 1)
            agent_name = "{}-{}".format(name, int(number) + 1)
            if store:
                self._stored.agents.append(agent_name)
        else:
            agent_name = self.unit.name.replace('/', '-')
            if store:
                self._stored.agents = []
                self._stored.agents.append(agent_name)
        return agent_name


if __name__ == '__main__':
    main(JenkinsAgentCharm)
