# Integrations

### agent

_Interface_: jenkins_agent_v0  
_Supported charms_: [jenkins](https://charmhub.io/jenkins)

Agent integration is a required relation for the Jenkins agent charm to supply the job execution output to Jenkins.

Example agent integrate command: 
```
juju integrate jenkins jenkins-agent-k8s
```
