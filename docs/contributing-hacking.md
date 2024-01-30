For any problems with this charm, please [report bugs here](https://bugs.launchpad.net/charm-k8s-jenkins-agent).

The code for this charm can be downloaded as follows:

```
git clone https://git.launchpad.net/charm-k8s-jenkins-agent
```

To run tests, simply run  `make test`  from within the charm code directory.

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