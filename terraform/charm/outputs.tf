# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "application" {
  description = "The deployed application object."
  value       = juju_application.jenkins_agent_k8s
}

output "provides" {
  description = "Map of the provided integration endpoints."
  value = {
    agent = {
      kind     = "endpoint"
      name     = juju_application.jenkins_agent_k8s.name
      endpoint = "agent"
    }
  }
}
