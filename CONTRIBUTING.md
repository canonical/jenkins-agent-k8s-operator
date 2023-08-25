# Contributing

Build the OCI image:

```bash
cd jenkins_agent_k8s_rock
rockcraft
```

Push the OCI image to microk8s:
(Note that the microk8s registry needs to be enabled using `microk8s enable registry`.)

```bash
sudo /snap/rockcraft/current/bin/skopeo --insecure-policy copy oci-archive:jenkins_agent_k8s_rock/jenkins-agent-k8s_1.0_amd64.rock docker-daemon:jenkins-agent:1.0
sudo docker tag jenkins-agent:1.0 localhost:32000/jenkins-agent:1.0
sudo docker push localhost:32000/jenkins-agent:1.0
```

Deploy the charm:

```bash
charmcraft pack
juju deploy ./jenkins-agent-k8s_ubuntu-22.04-amd64.charm --resource jenkins-image=localhost:32000/jenkins-agent:1.0
```

## Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
