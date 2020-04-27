#!/usr/bin/env python3

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main


class JenkinsSlaveCharm(CharmBase):
    state = StoredState()

    def __init__(self, framework, parent):
        super().__init__(framework, parent)

        framework.observe(self.on.install, self)
        framework.observe(self.on.upgrade_charm, self)
        framework.observe(self.on.run_action, self)

    def on_install(self, event):
        pass

    def on_upgrade_charm(self, event):
        pass

    def on_config_changed(self, event):
        pass


if __name__ == '__main__':
    main(JenkinsSlaveCharm)
