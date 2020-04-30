#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import io
import pprint
import os
import sys
import logging

from ops.charm import CharmBase
from ops.framework import StoredState, EventSource, EventBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus


logger = logging.getLogger()


def generate_pod_config(config, secured=True):
    """Kubernetes pod config generator.

    generate_pod_config generates Kubernetes deployment config.
    If the secured keyword is set then it will return a sanitised copy
    without exposing secrets.
    """
    pod_config = {}

    pod_config["JENKINS_API_USER"] = config["jenkins_user"]
    if config.get("jenkins_master_url", None):
        pod_config["JENKINS_URL"] = config["jenkins_master_url"]
    if config.get("jenkins_agent_name", None):
        pod_config["JENKINS_HOSTNAME"] = config["jenkins_agent_name"]

    if secured:
        return pod_config

    # Add secrets from charm config
    pod_config["JENKINS_API_TOKEN"] = config["jenkins_api_token"]

    return pod_config


class SlaveRelationConfigureEvent(EventBase):
    pass


class JenkinsAgentCharm(CharmBase):
    state = StoredState()

    on_slave_relation_configured = EventSource(SlaveRelationConfigureEvent)

    def __init__(self, framework, parent):
        super().__init__(framework, parent)

        framework.observe(self.on.start, self.configure_pod)
        framework.observe(self.on.config_changed, self.configure_pod)
        framework.observe(self.on.upgrade_charm, self.configure_pod)
        framework.observe(self.on_slave_relation_configured, self.configure_pod)

        self.state.set_default(_spec=None)

    def on_upgrade_charm(self, event):
        pass

    def on_config_changed(self, event):
        pass

    def configure_pod(self, event):
        is_valid = self.is_valid_config()
        if not is_valid:
            return

        spec = self.make_pod_spec()
        if spec != self.state._spec:
            self.state._spec = spec
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

        self.state.is_started = True
        self.model.unit.status = ActiveStatus()

    def make_pod_spec(self):
        config = self.model.config
        full_pod_config = generate_pod_config(config, secured=False)
        secure_pod_config = generate_pod_config(config, secured=True)

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
        is_valid = True
        config = self.model.config

        want = ("image", "jenkins_user", "jenkins_api_token")
        missing = [k for k in want if config[k].rstrip() == ""]
        if missing:
            message = "Missing required config: {}".format(" ".join(missing))
            logger.info(message)
            self.model.unit.status = BlockedStatus(message)
            is_valid = False

        return is_valid

    def on_jenkins_relation_joined(self, event):
        self.log.info("Jenkins relation joined")
        self.configure_slave_through_relation(event.relation)

    def configure_slave_through_relation(self, rel):
        self.log.info("Setting up jenkins via slave relation")
        self.model.unit.status = MaintenanceStatus("Configuring jenkins slave")

        if config.get("master_url"):
            self.log.info("Config option 'master_url' is set. Can't use slave relation.")
            self.model.unit.status = ActiveStatus()
            return

        url = rel.data[self.model.unit]["url"]
        if url:
            config["master_url"] = url
        else:
            self.log.info("Master hasn't exported its url yet. Continuing with the configured master_url.")
            self.model.unit.status = ActiveStatus()
            return

        noexecutors = os.cpu_count()
        config_labels = config.get('labels')

        if config_labels:
            labels = config_labels
        else:
            labels = os.uname()[4]

        rel.data[self.model.unit]["executors"] = noexecutors
        rel.data[self.model.unit]["labels"] = labels

        self.on.slave_relation_configured.emit()


if __name__ == '__main__':
    main(JenkinsAgentCharm)
