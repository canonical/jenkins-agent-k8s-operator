# How to upgrade

To upgrade the jenkins-agent-k8s charm, use the [`juju refresh`](https://documentation.ubuntu.com/juju/3.6/reference/juju-cli/list-of-juju-cli-commands/refresh/) command.
Since jenkins-agent-k8s does not manage any persistent data or databases, there are no backup or migration steps required before upgrading.

Before performing an upgrade, ensure that your Juju model is in a healthy state:

```bash
juju status
```

Confirm that all units are active and idle.

## Refresh to the latest revision

To upgrade jenkins-agent-k8s to the latest revision from Charmhub:

```bash
juju refresh jenkins-agent-k8s
```

This command will pull and apply the most recent revision of the jenkins-agent-k8s charm from the same channel it was originally deployed from.

## Verify the upgrade

After the refresh completes, confirm that the charm and its units are active:

```bash
juju status jenkins-agent-k8s
```

The application status should display as:

```
Active   jenkins-agent-k8s/0  ...
```