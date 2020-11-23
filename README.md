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

### Deploy Jenkins locally using LXC

First we're going to bootstrap and deploy Juju on LXC. We'll later add our
MicroK8s model to this same controller.
```
juju bootstrap localhost lxd
juju deploy jenkins
```
Then go on the jenkins interface and create a permanent node called "jenkins-agent-k8s-test"
manually for now. Grab the following variables for later use:

```
export JENKINS_API_TOKEN=$(juju ssh 0 -- sudo cat /var/lib/jenkins/.admin_token)
export JENKINS_IP=$(juju status --format json jenkins | jq -r '.machines."0"."ip-addresses"[0]')
```

### Deploy the jenkins-agent charm

You need to have a jenkins charm deployed locally and have the following variables
defined. See the "[Deploy Jenkins locally](#deploy-jenkins-locally)" section.

* JENKINS_API_TOKEN: the token for the admin user of your jenkins charm
* JENKINS_IP: the IP of your jenkins charm instance

In this repository directory
```
microk8s.config | juju add-k8s micro --controller=lxd
juju add-model jenkins-agent-k8s
juju model-config logging-config="<root>=DEBUG"
juju deploy cs:~jenkins-ci-charmers/jenkins-agent \
  --config "jenkins_agent_name=jenkins-agent-k8s-test" \
  --config "jenkins_api_token=${JENKINS_API_TOKEN:?}" \
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
