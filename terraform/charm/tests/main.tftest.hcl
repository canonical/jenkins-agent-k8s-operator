# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variables {
  app_name    = "jenkins-agent-k8s"
  base        = "ubuntu@22.04"
  channel     = "latest/edge"
  config      = {}
  constraints = "arch=amd64"
  model_uuid  = "00000000-0000-0000-0000-000000000001"
  resources   = {}
  revision    = 10
  units       = 2
}

mock_provider "juju" {
  mock_resource "juju_application" {
    override_during = plan
    defaults = {
      id         = "jenkins-agent-k8s"
      model_type = "kubernetes"
    }
  }
}

run "deploys_application" {
  command = plan

  assert {
    condition     = output.application.name == "jenkins-agent-k8s" && output.application.model_uuid == "00000000-0000-0000-0000-000000000001" && output.application.charm[0].name == "jenkins-agent-k8s" && output.application.charm[0].channel == "latest/edge" && output.application.charm[0].base == "ubuntu@22.04" && output.application.charm[0].revision == 10
    error_message = "application identity did not match the expected deployment"
  }

  assert {
    condition     = output.application.constraints == "arch=amd64"
    error_message = "application constraints did not match expected"
  }

  assert {
    condition     = output.application.units == 2
    error_message = "application units did not match expected"
  }

  assert {
    condition = output.provides == {
      agent = {
        kind     = "endpoint"
        name     = "jenkins-agent-k8s"
        endpoint = "agent"
      }
    }
    error_message = "relation outputs did not match expected structure"
  }
}
