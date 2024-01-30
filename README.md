[![CharmHub Badge](https://charmhub.io/jenkins-agent-k8s/badge.svg)](https://charmhub.io/jenkins-agent-k8s)
[![Publish to edge](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/jenkins-agent-k8s-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# Jenkins Agent k8s operator

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) deploying and managing [Jenkins](https://www.jenkins.io/) agents on Kubernetes, configurable to use a Jenkins charm deployed in another Juju model, or to connect to a standalone Jenkins instance.

This charm simplifies initial deployment and "day N" operations of Jenkins Agent on Kubernetes. It allows for deployment on many  different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to [Charmed Kubernetes](https://ubuntu.com/kubernetes/charmed-k8s) and public cloud Kubernetes offerings.

As such, the charm makes it easy for those looking to take control of their own Agents whilst keeping operations simple, and gives them the freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating Jenkins Agent simple and straightforward through Juju's clean interface. It will allow easy deployment into multiple environments for testing changes, and supports scaling out for enterprise deployments.

## Project and community

The Jenkins agent k8s operator is a member of the Ubuntu family. It's an open source project that warmly welcomes community  projects, contributions, suggestions, fixes and constructive feedback.
* [Code of conduct](https://ubuntu.com/community/code-of-conduct)
* [Get support](https://discourse.charmhub.io/)
* [Join our online chat](https://app.element.io/#/room/#charmhub-charmdev:ubuntu.com)
* [Contribute](https://charmhub.io/jenkins-agent-k8s-operator/docs/how-to-contribute)
Thinking about using the Jenkins agent k8s operator for your next project?[Get in touch](https://app.element.io/#/room/#charmhub-charmdev:ubuntu.com)!

---

For further details,
[see the charm's detailed documentation](https://charmhub.io/jenkins-agent-k8s).

