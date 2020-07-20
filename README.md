# Jenkins agent operator charm
This charm sets up a jenkins-agent in kubernetes.

To prepare this charm for deployment, run the following to install the
framework in to the `lib/` directory:

```
git submodule add https://github.com/canonical/operator mod/operator
```

Link the framework:
```
ln -s ../mod/operator/ops lib/ops
```

Update the operator submodule:
```
git submodule update --init
```

## Testing the docker image

```
juju deploy jenkins
```

Then go on the jenkins interface and create a permanent node called "jenkins-agent-k8s-test" manually for now.

```
export JENKINS_API_TOKEN=$(juju ssh 0 -- sudo cat /var/lib/jenkins/.admin_token)
export JENKINS_IMAGE="jenkins-agent-k8s:devel"
export JENKINS_IP=$(juju status --format json jenkins | jq -r '.machines."0"."ip-addresses"[0]')
make build-image
docker run --rm -ti --name jenkins-agent-test \
 -e JENKINS_API_USER=admin \
 -e JENKINS_API_TOKEN="${JENKINS_API_TOKEN}" \
 -e JENKINS_URL="http://${JENKINS_IP}:8080" \
 -e JENKINS_HOSTNAME="jenkins-agent-test" "${JENKINS_IMAGE}"
```

## Testing with microk8s

### Install prerequisites
```
sudo snap install --channel 2.8/beta juju --classic
sudo snap install microk8s --classic
sudo snap install docker

# Start microk8s and enable needed modules
microk8s.start
microk8s.enable registry dns storage
juju bootstrap microk8s micro
```

### Build the jenkins-agent-k8s image

You need to have a a jenkins charm deployed locally and have the following variables
defined. See the "[Testing the docker image](#testing-the-docker-image)" section.

* JENKINS_API_TOKEN: the token for the admin user of your jenkins charm

* JENKIN_IP: the ip of your jenkins charm instance

In this repository directory
```
export JENKINS_IMAGE="localhost:32000/jenkins-agent-k8s:devel"
export MODEL=jenkins-agent-k8s
make build-image
docker save "${JENKINS_IMAGE}" > /var/tmp/"${JENKINS_IMAGE##*/}".tar
microk8s.ctr image import /var/tmp/"${JENKINS_IMAGE##*/}".tar
juju add-model "${MODEL}"
juju model-config logging-config="<root>=DEBUG"
juju deploy . \
  --config "jenkins_agent_name=jenkins-agent-k8s-test" \
  --config "jenkins_api_token=${JENKINS_API_TOKEN:?}" \
  --config "jenkins_master_url=http://${JENKINS_IP:?}:8080" \
  --config "image=${JENKINS_IMAGE}"
```

Once everything is deployed, you can check the logs with
```
microk8s.kubectl -n "${MODEL}" logs -f --all-containers=true deployment/jenkins-agent
```


