# Jenkins agent operator charm
This charm sets up a jenkins-agent in kubernetes.

## Testing with MicroK8s

### Install prerequisites
```
sudo snap install juju --classic
sudo snap install microk8s --classic

# Start MicroK8s and enable needed modules
microk8s.start
microk8s.enable dns storage
```

### Using Cross-model Relations

The charm supports cross-model relations to connect to a Juju-deployed Jenkins
instance in another model.

First we're going to bootstrap and deploy Juju on LXC. We'll later add our
MicroK8s model to this same controller.
```
juju bootstrap localhost lxd
juju deploy jenkins --config password=admin
```
Then go to the jenkins interface by visiting `$JENKINS_IP:8080` in a browser,
and logging in with the username `admin` and password `admin` (as set in
config above). You can configure the plugins you want, and either create an
initial admin user or skip that and continue with the pre-created one.

Now we're going to create our k8s model and generate a cross-model relation
offer:
```
microk8s.config | juju add-k8s micro --controller=lxd
juju add-model jenkins-agent-k8s micro
juju deploy cs:~jenkins-ci-charmers/jenkins-agent
```
The charm status will be "Blocked" with a message of "Missing required config:
jenkins_agent_name jenkins_agent_token jenkins_master_url". This will be fixed
by creating and accepting our cross-model relation. We do this from within the
k8s model:
```
juju offer jenkins-agent:slave
# The output will be something like:
#  Application "jenkins-agent" endpoints [slave] available at "admin/jenkins-agent-k8s.jenkins-agent"
```
Switch back to your IaaS model where you deployed jenkins and run:
```
# Adjust based on the output of your 'juju offer' command above
juju add-relation jenkins <your-controller>:admin/<your-microk8s-model>.jenkins-agent
```
You can now visit `$JENKINS_IP:8080/computer/` in a browser and you'll see the
jenkins agent has been added to your jenkins instance.

### Using a Manually Configured Node

The charm also supports adding nodes manually, as we'll see below. This would
allow you to manually connect to a Jenkins instance in another Juju model, or
even to connect to a Jenkins instance that's not managed by Juju.

#### Deploy Jenkins locally using LXC

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

#### Deploy the jenkins-agent charm

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

## Testing the docker image

Deploy Jenkins locally per the section above, including setting the relevant variables,
then build the image locally as follows:
```
make build-image
docker run --rm -ti --name jenkins-agent-test \
 -e JENKINS_API_USER=admin \
 -e JENKINS_API_TOKEN="${JENKINS_API_TOKEN}" \
 -e JENKINS_URL="http://${JENKINS_IP}:8080" \
 -e JENKINS_HOSTNAME="jenkins-agent-test" "jenkins-agent-k8s:devel"
```
