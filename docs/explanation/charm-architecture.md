# Charm architecture

At its core, [Jenkins agents](https://www.jenkins.io/doc/book/managing/nodes/#components-of-distributed-builds) are [Java](https://www.java.com/en/) applications executing the jobs on behalf of [Jenkins](https://www.jenkins.io/) itself.

The charm design leverages the [sidecar](https://kubernetes.io/blog/2015/06/the-distributed-system-toolkit-patterns/#example-1-sidecar-containers) pattern to allow multiple containers in each pod with [Pebble](https://juju.is/docs/sdk/pebble) running as the workload container’s entrypoint.

Pebble is a lightweight, API-driven process supervisor that is responsible for configuring processes to run in a container and controlling those processes throughout the workload lifecycle.

Pebble `services` are configured through [layers](https://github.com/canonical/pebble#layer-specification), and the following containers represent each one a layer forming the effective Pebble configuration, or `plan`:

1. An [Jenkins agent](https://www.jenkins.io/doc/book/managing/nodes/#components-of-distributed-builds) container, which manages the CI jobs.


As a result, if you run a `kubectl get pods` on a namespace named for the Juju model you've deployed the Jenkins agent k8s charm into, you'll see something like the following:

```bash
NAME                             READY   STATUS            RESTARTS   AGE
jenkins-agent-k8s-0              2/2     Running           0          2m2s
```

This shows there are 2 containers - the Jenkins agent one and container for the charm code itself.

And if you run `kubectl describe pod jenkins-agent-k8s-0`, all the containers will have as Command ```/charm/bin/pebble```. That's because Pebble is responsible for the processes startup as explained above.

## OCI images

We use [Rockcraft](https://canonical-rockcraft.readthedocs-hosted.com/en/latest/) to build the OCI Image for the Jenkins agent. 
The image is defined in the [Jenkins agent k8s ROCK](https://github.com/canonical/jenkins-agent-k8s-operator/blob/main/jenkins_agent_k8s_rock/).
They are published to [Charmhub](https://charmhub.io/), the official repository of charms.
This is done by publishing a resource to Charmhub as described in the [Juju SDK How-to guides](https://juju.is/docs/sdk/publishing).

## Containers

Configuration files for the containers can be found in the respective directories that define the ROCKs, see the section above.

### Jenkins agent k8s

This container manages the task execution on behalf of the Jenkins controller by using executors. It contains an agent, a small  Java client process that connects to a Jenkins controller and is assumed to be unreliable. Any tools required for building and testing get installed on this container, where the agent runs.

The workload that this container is running is defined in the [Jenkins agent k8s ROCK](https://github.com/canonical/jenkins-agent-k8s-operator/blob/main/jenkins_agent_k8s_rock/).

## Integrations

### Jenkins

The [Jenkins](https://charmhub.io/jenkins-k8s) controller, a CI server for which this agent charm will run tasks.

## Juju events

According to the [Juju SDK](https://juju.is/docs/sdk/event): "an event is a data structure that encapsulates part of the execution context of a charm".

For this charm, the following events are observed:

1. [jenkins_agent_k8s_pebble_ready](https://juju.is/docs/sdk/container-name-pebble-ready-event): fired on Kubernetes charms when the requested container is ready.
Action: wait for the integrations and configuration, download the JAR, configure the container and replan the service.
2. [config_changed](https://juju.is/docs/sdk/config-changed-event): usually fired in response to a configuration change using the CLI.
Action: wait for the integrations and configuration, download the JAR, configure the container and replan the service.
3. [upgrade_charm](https://juju.is/docs/sdk/upgrade-charm-event): fired when a charm upgrade is triggered.
Action: wait for the integrations and configuration, download the JAR, configure the container and replan the service.
4. [agent_relation_joined](https://juju.is/docs/sdk/relation-name-relation-joined-event): emitted when a unit joins the relation.
Action: download the JAR, configure the container and replan the service.
5. [agent_relation_changed](https://juju.is/docs/sdk/relation-name-relation-changed-event): triggered when another unit involved in the relation changed the data in the relation databag.
Action: download the JAR, configure the container and replan the service.
6. [agent_relation_departed](https://juju.is/docs/sdk/relation-name-relation-departed-event): fired when a unit departs the relation.
Action: stop the service.

## Charm code overview

The `src/charm.py` is the default entry point for a charm and has the JenkinsAgentCharm Python class which inherits from CharmBase.

CharmBase is the base class from which all Charms are formed, defined by [Ops](https://juju.is/docs/sdk/ops) (Python framework for developing charms).

See more information in [Charm](https://juju.is/docs/sdk/constructs#heading--charm).

The `__init__` method guarantees that the charm observes all events relevant to its operation and handles them.

Take, for example, when a configuration is changed by using the CLI.

1. User runs the command
```bash
juju config jenkins_agent_name=agent-one
```
2. A `config-changed` event is emitted
3. In the `__init__` method is defined how to handle this event like this:
```python
self.framework.observe(self.on.config_changed, self._on_config_changed)
```
4. The method `_on_config_changed`, for its turn,  will take the necessary actions such as waiting for all the relations to be ready and then configuring the containers.