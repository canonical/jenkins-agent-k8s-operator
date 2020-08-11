#!/usr/bin/env python3

# Copyright 2020 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import io
import pprint
import os
import sys
import logging

sys.path.append('lib')  # noqa: E402

from ops.charm import CharmBase
from ops.framework import StoredState, EventSource, EventBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus


logger = logging.getLogger()


class JenkinsAgentCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, framework, parent):
        super().__init__(framework, parent)

        framework.observe(self.on.start, self.configure_pod)
        framework.observe(self.on.config_changed, self.configure_pod)
        framework.observe(self.on.upgrade_charm, self.configure_pod)

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
        elif config.get("jenkins_master_url", None):
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
        is_valid = self.is_valid_config()
        if not is_valid:
            return

        if not self.unit.is_leader():
            self.unit.status = ActiveStatus()
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
        logger.info("This is the Kubernetes Pod spec config (sans secrets) <<EOM\n{}\nEOM".format(out.getvalue()))

        secure_pod_config.update(full_pod_config)
        return spec

    def is_valid_config(self):
        is_valid = True

        config = self.model.config
        if self._stored.agent_tokens:
            want = ("image")
        else:
            want = ("image", "jenkins_master_url", "jenkins_agent_name", "jenkins_agent_token")
        missing = [k for k in want if config[k].rstrip() == ""]
        if missing:
            message = "Missing required config: {}".format(" ".join(missing))
            logger.info(message)
            self.model.unit.status = BlockedStatus(message)
            is_valid = False

        return is_valid


if __name__ == '__main__':
    main(JenkinsAgentCharm)
