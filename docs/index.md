# Jenkins agent K8s operator

A [Juju](https://juju.is/) [charm](https://documentation.ubuntu.com/juju/3.6/reference/charm/) deploying and managing [Jenkins](https://www.jenkins.io/) agents on Kubernetes. This charm is configurable to use with a Jenkins charm deployed in another Juju model, or to connect to a standalone Jenkins instance.

This charm simplifies initial deployment and operations of Jenkins agents on Kubernetes. It allows for deployment on many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to [Charmed Kubernetes](https://ubuntu.com/kubernetes/charmed-k8s) and public cloud Kubernetes offerings.

For DevOps or SRE teams this charm will make operating Jenkins agent simple and straightforward through Juju's clean interface. It will allow easy deployment into multiple environments for testing changes, and supports scaling out for enterprise deployments.

## In this documentation

| | |
|--|--|
|  [Tutorials](https://charmhub.io/jenkins-agent-k8s/docs/tutorial-getting-started)</br>  Get started - a hands-on introduction to using the Charmed Indico operator for new users </br> |  [How-to guides](https://charmhub.io/jenkins-agent-k8s/docs/how-to-contribute) </br> Step-by-step guides covering key operations and common tasks |
| [Reference](https://charmhub.io/jenkins-agent-k8s/docs/reference-actions) </br> Technical information - specifications, APIs, architecture | [Explanation](https://charmhub.io/jenkins-agent-k8s/docs/explanation-charm-architecture) </br> Concepts - discussion and clarification of key topics  |


## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/t/jenkins-agent-documentation-overview/3982) to enable easy collaboration. Please use the "Help us improve this documentation" links on each documentation page to either directly change something you see that's wrong, ask a question, or make a suggestion about a potential change via the comments section.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/jenkins-agent-k8s-operator/issues).

## Project and community

The jenkins-agent-k8s charm is a member of the Ubuntu family. It's an open-source project that warmly welcomes community 
projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](https://github.com/canonical/jenkins-agent-k8s-operator/blob/9b7b1452328b185d0149eedde29e5746b057893b/CONTRIBUTING.md)

Thinking about using the jenkins-agent-k8s charm for your next project? 
[Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)!

# Contents

1. [Tutorial](tutorial)
  1. [Quick guide](tutorial/getting-started.md)
1. [How To](how-to)
  1. [Contribute](how-to/contribute.md)
  1. [Upgrade](how-to/upgrade.md)
1. [Reference](reference)
  1. [Actions](reference/actions.md)
  1. [Charm architecture](reference/charm-architecture.md)
  1. [Configurations](reference/configurations.md)
  1. [Integrations](reference/integrations.md)
1. [Explanation](explanation)
1. [Changelog](changelog.md)