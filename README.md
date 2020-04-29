# Jenkins slave operator charm
This charm sets up a jenkins-slave in kubernetes.

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

Go create a node on the jenkins master called "jenkins-slave-test" manually for now

```
API_TOKEN=$(juju ssh 0 -- sudo cat /var/lib/jenkins/.admin_token)
JENKINS_IP=$(juju status --format json jenkins | jq -r '.machines."0"."ip-addresses"[0]')
make build-image-dev
docker run --rm -ti --name jenkins-slave-test \
 -e JENKINS_API_USER=admin \
 -e JENKINS_API_TOKEN="${API_TOKEN}" \
 -e JENKINS_URL="http://${JENKINS_IP}:8080" \
 -e JENKINS_HOSTNAME="jenkins-slave-test" jenkins-slave-operator:devel
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

### Build the jenkins-slave-operator image

In this repository directory
```
make build-dev-image
docker save jenkins-slave-operator:devel > /var/tmp/jenkins-slave-operator.tar
microk8s.ctr image import /var/tmp/jenkins-slave-operator.tar
juju add-model jenkins-slave-operator
juju model-config logging-config="<root>=DEBUG"
juju deploy . \
  --config "jenkins_agent_name=jenkins-slave-test" \
  --config "jenkins_api_token=${JENKINS_API_TOKEN}" \
  --config "jenkins_master_url=http://${JENKINS_IP}:8080" \
  --config "image=jenkins-slave-operator:devel"
```


