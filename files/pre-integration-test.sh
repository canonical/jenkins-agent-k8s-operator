#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# Jenkins charm is deployed on lxd and Jenkins agent charm is deployed on microk8s

# Enure setup of microk8s.

# lxd should be install and init by a previous step in integration test action.
echo "bootstraping lxd juju controller"
sg microk8s -c "microk8s status --wait-ready"
sg microk8s -c "juju bootstrap localhost localhost"

echo "Deploying jenkins"
sg microk8s -c "python3 tests/integration/deploy_jenkins.py"

echo "bootstraping microk8s juju controller"
sg microk8s -c "juju bootstrap microk8s micro"
sg microk8s -c "juju add-model testing -c micro"
sg microk8s -c "juju switch micro:admin/testing"
sg microk8s -c "microk8s status --wait-ready"
