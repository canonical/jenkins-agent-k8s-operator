## Continuous Integration and Continuous Delivery

As an extensible automation server, Jenkins can be used as a simple CI server or turned into the continuous delivery hub for any project.

## Plugins

With hundreds of plugins in the Update Center, Jenkins integrates with practically every tool in the continuous integration and continuous delivery toolchain.

---

For details on configuration options, see [this page](https://charmhub.io/jenkins-agent/configure).

## Future Improvements

Currently the charm only supports one unit per application when using relations. If new units are added they fail to connect to Jenkins.

This is feature is being tracked in this [bug](https://bugs.launchpad.net/charm-k8s-jenkins-agent/+bug/1928022).

If more units are needed while this is not available, deploy additional applications with a different name, such as:

```
juju deploy jenkins-agent-k8s jenkins-agent-one
```

# Contents

1. [Contributing](contributing-hacking.md)
1. [Relations](relations.md)