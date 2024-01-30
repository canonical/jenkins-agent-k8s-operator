# Quick guide

## What you’ll do

- Deploy the [Jenkins k8s agent charm](https://charmhub.io/jenkins-agent-k8s).
- Integrate with [the Jenkins charm](https://charmhub.io/jenkins)

Through the process, you'll inspect the Kubernetes resources created and verify the workload state.

## Requirements

- Juju 3 installed.
- Juju controller and model created.

For more information about how to install Juju, see [Get started with Juju](https://juju.is/docs/olm/get-started-with-juju).

### Deploy the Jenkins k8s agent charm

Since the Jenkins k8s agent charm requires a connection to Jenkins, you'll deploy the Jenkins charm too. For more information, see [Charm Architecture](https://charmhub.io/indico/jenkins-agent-k8s/explanation-charm-architecture).


Deploy the charms:

```bash
juju deploy jenkins-agent-k8s
juju deploy jenkins-k8s
```

To see the pod created by the Jenkins k8s agent charm, run `kubectl get pods` on a namespace named for the Juju model you've deployed the charm into. The output is similar to the following:

```bash
NAME                             READY   STATUS            RESTARTS   AGE
jenkins-agent-k8s-0              2/2     Running           0          2m2s
```

Run [`juju status`](https://juju.is/docs/olm/juju-status) to see the current status of the deployment. In the Unit list, you can see that Jenkins k8s agent is waiting:

```bash
jenkins-agent-k8s/0*  blocked   idle   10.1.180.75         Waiting for config/relation.
```

This means that Jenkins k8s agent charm isn't integrated with Jenkins yet.

### Integrate with the Jenkins charm

Provide integration between Jenkins k8s agent and Jenkins by running the following [`juju integrate`](https://juju.is/docs/juju/juju-integrate) command:

```bash
juju integrate jenkins-k8s jenkins-agent-k8s
```

Run `juju status` and wait until the Application status is `Active` as the following example:

Optional: run `juju status --relations --watch 5s` to watch the status every 5 seconds with the Relations section.

```bash
App                Version  Status   Scale  Charm              Channel  Rev  Address         Exposed  Message
jenkins-agent-k8s           active       1  jenkins-agent-k8s  stable    18  10.152.183.135  no       

```

The deployment finishes when the status shows "Active".
