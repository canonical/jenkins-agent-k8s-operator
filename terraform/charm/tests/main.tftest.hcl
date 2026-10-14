# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

run "setup_tests" {
  module {
    source = "./tests/setup"
  }
}

run "basic_deploy" {
  variables {
    model_uuid = run.setup_tests.model_uuid
    base       = "ubuntu@24.04"
    channel    = "latest/edge"
    # renovate: depName="jenkins-agent-k8s"
    revision = 77
  }

  assert {
    condition     = output.application.name == "jenkins-agent-k8s"
    error_message = "jenkins-agent-k8s application name did not match expected"
  }

  assert {
    condition     = output.provides.value.endpoint == "agent"
    error_message = "jenkins-agent-k8s module should provide 'provides.value' output"
  }
}
