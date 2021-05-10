# Jenkins Agent Operator

A Juju charm deploying and managing Jenkins Agent on Kubernetes, configurable to
use a Jenkins charm deployed in another Juju model, or to connect to a
standalone Jenkins instance.

## Overview

Jenkins is a self-contained, open source automation server which can be used
to automate all sorts of tasks related to building, testing, and delivering or
deploying software.

For documentation on Jenkins itself, [see here](https://www.jenkins.io/doc/).

## Usage

For details on using Kubernetes with Juju [see here](https://juju.is/docs/kubernetes), and for details on using
Juju with MicroK8s for easy local testing [see here](https://juju.is/docs/microk8s-cloud).

The charm supports cross-model relations to connect to a Juju-deployed Jenkins
instance in another model. We'll use this to deploy a Jenkins instance and
connect our Jenkins Agent to it.

First we're going to bootstrap and deploy Juju on LXC. We'll later add our
MicroK8s model to this same controller.

```bash
juju bootstrap localhost lxd
juju deploy jenkins --config jnlp-port=-1
```

The default password for the 'admin' account will be auto-generated. Retrieve it using:

```bash
juju run-action jenkins/0 get-admin-credentials --wait
```

Then go to the jenkins interface by visiting `$JENKINS_IP:8080` in a browser,
and logging in with the username `admin` and password (as obtained through the command above).
 You can configure the plugins you want, and either create an
initial admin user or skip that and continue with the pre-created one.

Now we're going to create our k8s model and generate a cross-model relation
offer:

```bash
microk8s.config | juju add-k8s micro --controller=lxd
juju add-model jenkins-agent-k8s micro
charmcraft pack
juju deploy ./alejdg-jenkins-agent-k8s.charm --resource jenkins-agent-image=jenkinscicharmers/jenkinsagent:edge
```

The charm status will be "Blocked" with a message of "Missing required config:
jenkins_agent_name jenkins_agent_token jenkins_url". This will be fixed
by creating and accepting our cross-model relation. We do this from within the
k8s model:

```bash
juju offer jenkins-agent:slave
# The output will be something like:
#  Application "jenkins-agent" endpoints [slave] available at "admin/jenkins-agent-k8s.jenkins-agent"
```

Switch back to your IaaS model where you deployed jenkins and run:

```bash
# Adjust based on the output of your 'juju offer' command above
juju add-relation jenkins <your-controller>:admin/<your-microk8s-model>.jenkins-agent
```

You can now visit `$JENKINS_IP:8080/computer/` in a browser and you'll see the
jenkins agent has been added to your jenkins instance.

---

For more details [see here](https://charmhub.io/alejdg-jenkins-agent-k8s/docs).
