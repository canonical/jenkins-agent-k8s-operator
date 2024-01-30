The charm supports cross-model relations, and deployment instructions for this are [documented here](https://charmhub.io/jenkins-agent).

However, the charm also supports connecting to a manually configured Jenkins instance.

## Using a Manually Configured Node

The charm also supports adding nodes manually, as we'll see below. This would
allow you to manually connect to a Jenkins instance in another Juju model, or
even to connect to a Jenkins instance that's not managed by Juju.

### Deploy Jenkins locally using LXC

First we're going to bootstrap and deploy Juju on LXC. We'll later add our
MicroK8s model to this same controller.
```
juju bootstrap localhost lxd
juju deploy jenkins --config password=admin
```
Then go on the jenkins interface and create a permanent node called "jenkins-agent-k8s-test"
manually for now. You can do this by visiting `$JENKINS_IP:8080` in a browser,
and logging in with username `admin` and password `admin` (as set in config
above). Once you've installed the plugins you want, and created an initial
admin user you can then click the "Create an agent" link. You'll be asked to
set the "remote root directory", which you should set to `/var/lib/jenkins`.
If you see a message about "Either WebSocket mode is selected, or the TCP port
for inbound agents must be enabled" when creating an agent, under the "Use
WebSocket" checkbox, go to `$JENKINS_IP:8080/configureSecurity/` and under the
"Agents" section, set "TCP port for inbound agents" to "Fixed" with a port of
8081.

Grab the following variables for later use:
```
# Set this to the value displayed for -secret on $JENKINS_IP:8080/computer/$AGENT_NAME/
export JENKINS_AGENT_TOKEN=SOME_VALUE_PER_URL_ABOVE
export JENKINS_IP=$(juju status --format json jenkins | jq -r '.machines."0"."ip-addresses"[0]')
```

### Deploy the jenkins-agent charm

You need to have a jenkins charm deployed locally and have the following variables
defined. See the "[Deploy Jenkins locally](#deploy-jenkins-locally)" section.

* JENKINS_AGENT_TOKEN: the token for the jenkins agent
* JENKINS_IP: the IP of your jenkins charm instance

In this repository directory
```
microk8s.config | juju add-k8s micro --controller=lxd
juju add-model jenkins-agent-k8s micro
juju model-config logging-config="<root>=DEBUG"
juju deploy cs:~jenkins-ci-charmers/jenkins-agent \
  --config "jenkins_agent_name=jenkins-agent-k8s-test" \
  --config "jenkins_agent_token=${JENKINS_AGENT_TOKEN:?}" \
  --config "jenkins_master_url=http://${JENKINS_IP:?}:8080"
```

Once everything is deployed, you can check the logs with:
```
microk8s.kubectl -n jenkins-agent-k8s logs -f --all-containers=true deployment/jenkins-agent
```