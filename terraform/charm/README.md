<!-- vale Canonical.007-Headings-sentence-case = NO -->
# Jenkins-agent-k8s Terraform module
<!-- vale Canonical.007-Headings-sentence-case = YES -->

This folder contains a base [Terraform][Terraform] module for the Jenkins-agent-k8s charm.

The module uses the [Terraform Juju provider][Terraform Juju provider] to model the charm
deployment onto any Kubernetes environment managed by [Juju][Juju].

## Module structure

- **main.tf** - Defines the Juju application to be deployed.
- **variables.tf** - Allows customization of the deployment. Also models the charm configuration, 
  except for exposing the deployment options (Juju model name, channel or application name).
- **outputs.tf** - Integrates the module with other Terraform modules, primarily
  by defining potential integration endpoints (charm integrations), but also by exposing
  the Juju application name.
- **versions.tf** - Defines the Terraform provider version.

## Using jenkins-agent-k8s base module in higher level modules

If you want to use `jenkins-agent-k8s` base module as part of your Terraform module, import it
like shown below:

```text
data "juju_model" "my_model" {
  name = var.model
}

module "jenkins-agent-k8s" {
  source = "git::https://github.com/canonical/jenkins-agent-k8s-operator//terraform"

  model = juju_model.my_model.name
  # (Customize configuration variables here if needed)
}
```

Create integrations, for instance:

```text
resource "juju_integration" "jenkins-k8s-agent-agent-v0" {
  model = juju_model.my_model.name
  application {
    name     = module.jenkins_k8s.app_name
    endpoint = module.jenkins_k8s.requires.jenkins_agent_v0
  }
  application {
    name     = "jenkins-agent-k8s"
    endpoint = "agent"
  }
}
```

The complete list of available integrations can be found [in the Integrations tab][jenkins-agent-k8s-integrations].

[Terraform]: https://www.terraform.io/
[Terraform Juju provider]: https://registry.terraform.io/providers/juju/juju/latest
[Juju]: https://juju.is
[jenkins-agent-k8s-integrations]: https://charmhub.io/jenkins-agent-k8s/integrations
