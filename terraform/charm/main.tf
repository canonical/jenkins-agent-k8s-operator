# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "jenkins_agent_k8s" {
  name  = var.app_name
  model = var.model

  charm {
    name     = "jenkins-agent-k8s"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }

  config      = var.config
  constraints = var.constraints
  units       = var.units
}
