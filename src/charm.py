#!/usr/bin/env python3

import io
import pprint
import sys
import logging
from yaml import safe_load

sys.path.append('lib')  # noqa: E402

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus  # NoQA: E402


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


class JenkinsAgentCharm(CharmBase):
    state = StoredState()

    def __init__(self, framework, parent):
        super().__init__(framework, parent)

        framework.observe(self.on.start, self.configure_pod)
        framework.observe(self.on.config_changed, self.configure_pod)
        framework.observe(self.on.upgrade_charm, self.configure_pod)

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


if __name__ == '__main__':
    main(JenkinsAgentCharm)
