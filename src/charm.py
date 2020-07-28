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
    state = StoredState()

    # on_slave_relation_configured = EventSource(SlaveRelationConfigureEvent)

    def __init__(self, framework, parent):
        super().__init__(framework, parent)

        framework.observe(self.on.start, self.configure_pod)
        framework.observe(self.on.config_changed, self.configure_pod)
        framework.observe(self.on.upgrade_charm, self.configure_pod)
        framework.observe(self.on.slave_relation_joined, self.on_slave_relation_joined)
        framework.observe(self.on.slave_relation_changed, self.on_slave_relation_joined)

        self.state.set_default(_spec=None, jenkins_url=None, agent_token=None)

    def on_upgrade_charm(self, event):
        pass

    def on_config_changed(self, event):
        pass

    def generate_pod_config(self, config, secured=True):
        """Kubernetes pod config generator.

        generate_pod_config generates Kubernetes deployment config.
        If the secured keyword is set then it will return a sanitised copy
        without exposing secrets.
        """
        unit_name = self.unit.name.replace('/', '-')
        pod_config = {}

        pod_config["JENKINS_API_USER"] = config["jenkins_user"]
        pod_config["JENKINS_HOSTNAME"] = unit_name

        if self.state.jenkins_url:
            pod_config["JENKINS_URL"] = self.state.jenkins_url
        elif config.get("jenkins_master_url", None):
            pod_config["JENKINS_URL"] = config["jenkins_master_url"]
        # if config.get("jenkins_agent_name", None):
        #     pod_config["JENKINS_HOSTNAME"] = config["jenkins_agent_name"]

        if secured:
            return pod_config

        for i in self.state.agent_token:
            logger.info("ALEJDG - self.state.agent_token: %s", i)
            logger.info("ALEJDG - self.state.agent_token[%s]: %s", i, self.state.agent_token[i])
        pod_config["JENKINS_API_TOKEN"] = self.state.agent_token[unit_name] or config["jenkins_api_token"]

        return pod_config

    def configure_pod(self, event):
        is_valid = self.is_valid_config()
        if not is_valid:
            return

        # if not self.unit.is_leader():
        #     self.unit.status = ActiveStatus()
        #     return

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
        logger.info("ALEJDG - config type: %s - config data: %s", type(config), config)

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
        is_valid = True

        config = self.model.config
        if self.state.agent_token:
            want = ("image", "jenkins_user")
        else:
            want = ("image", "jenkins_user", "jenkins_api_token")
        missing = [k for k in want if config[k].rstrip() == ""]
        if missing:
            message = "Missing required config: {}".format(" ".join(missing))
            logger.info(message)
            self.model.unit.status = BlockedStatus(message)
            is_valid = False

        return is_valid

    def on_slave_relation_joined(self, event):
        logger.info("Jenkins relation joined")
        noexecutors = os.cpu_count()
        config_labels = self.model.config.get('labels')
        slave_host = self.unit.name.replace('/', '-')

        if config_labels:
            labels = config_labels
        else:
            labels = os.uname()[4]

        # slave_address = hookenv.unit_private_ip()

        logger.info("noexecutors: %s - type: %s",noexecutors, type(noexecutors))
        logger.info("labels: %s - type: %s",labels, type(labels))
        event.relation.data[self.model.unit]["executors"] = str(noexecutors)
        event.relation.data[self.model.unit]["labels"] = labels
        event.relation.data[self.model.unit]["slavehost"] = slave_host
        # event.relation.data[self.model.unit]["slaveaddress"] = slave_address

        remote_data = event.relation.data[event.app]
        logger.info("ALEJDG - remote_data_app: %s", remote_data)
        for i in remote_data:
            logger.info("ALEJDG - remote_data_app['%s']: %s", i, remote_data[i])

        if event.unit is not None:
            remote_data = event.relation.data[event.unit]
            logger.info("ALEJDG - os.environ: %s", os.environ)

        logger.info("ALEJDG - remote_data_post_app: %s", remote_data)
        for i in remote_data:
            logger.info("ALEJDG - remote_data_post_app['%s']: %s", i, remote_data[i])

        try:
            logger.info("ALEJDG - event.relation.data[event.unit]['url']: %s", event.relation.data[event.unit]['url'])
            logger.info("ALEJDG - event.relation.data[event.unit]['secret']: %s", event.relation.data[event.unit]['secret'])
            self.state.jenkins_url = event.relation.data[event.unit]['url']
            self.state.agent_token = {self.unit.name.replace('/', '-'):
                                      event.relation.data[event.unit]['secret']}
        except KeyError:
            pass

        self.configure_slave_through_relation(event)

    def on_slave_relation_changed(self, event):
        logger.info("Jenkins relation changed")
        self.on_slave_relation_joined(event)

    def configure_slave_through_relation(self, event):
        logger.info("Setting up jenkins via slave relation")
        self.model.unit.status = MaintenanceStatus("Configuring jenkins agent")

        if self.model.config.get("url"):
            logger.info("Config option 'url' is set. Can't use agent relation.")
            self.model.unit.status = ActiveStatus()
            return

        if self.state.jenkins_url is None:
            logger.info("Jenkins hasn't exported its url yet. Skipping setup for now.")
            self.model.unit.status = ActiveStatus()
            return

        if self.state.agent_token is None:
            logger.info("Jenkins hasn't exported the agent secret yet. Skipping setup for now.")
            self.model.unit.status = ActiveStatus()
            return

        elif self.state.agent_token[self.unit.name.replace('/', '-')] is None:
            logger.info("Jenkins hasn't exported the agent secret yet. Skipping setup for now.")
            self.model.unit.status = ActiveStatus()
            return

        self.configure_pod(event)


if __name__ == '__main__':
    main(JenkinsAgentCharm)
