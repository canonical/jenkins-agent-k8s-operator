[![CharmHub Badge](https://charmhub.io/jenkins-agent-k8s/badge.svg)](https://charmhub.io/jenkins-agent-k8s)
[![Publish to edge](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# Jenkins k8s Agent Operator

A Juju charm deploying and managing Jenkins agents on Kubernetes, configurable to use a Jenkins charm deployed in another Juju model, or to connect to a standalone Jenkins instance. [Jenkins](https://www.jenkins.io/) is a self-contained, open source automation server which can be used to automate all sorts of tasks related to building, testing, and delivering or deploying software.

This charm simplifies initial deployment and "day N" operations of Jenkins agents on Kubernetes. It allows for deployment on many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to [Charmed Kubernetes](https://ubuntu.com/kubernetes) to  public cloud Kubernetes offerings.

As such, the charm makes it easy for those looking to deploy their own continuous integration server with Jenkins, and gives them  the freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating Jenkins agents simple and straightforward through Juju's clean interface. It will allow easy deployment into multiple environments for testing of changes, and supports scaling out for enterprise deployments.

## Project and community

The Jenkins k8s agent Operator is a member of the Ubuntu family. It's an open source project that warmly welcomes community  projects, contributions, suggestions, fixes and constructive feedback.
* [Code of conduct](https://ubuntu.com/community/code-of-conduct)
* [Get support](https://discourse.charmhub.io/)
* [Join our online chat](https://app.element.io/#/room/#charmhub-charmdev:ubuntu.com)
* [Contribute](https://charmhub.io/indico/docs/how-to-contribute)
Thinking about using the Jenkins k8s agent Operator for your next project?[Get in touch](https://app.element.io/#/room/#charmhub-charmdev:ubuntu.com)!

---

For further details,
[see the charm's detailed documentation](https://charmhub.io/jenkins-agent-k8s).

