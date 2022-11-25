#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# Jenkins charm is deployed on lxd and Jenkins agent charm is deployed on microk8s

# Enure setup of microk8s.

# lxd should be install and init by a previous step in integration test action.
echo "bootstraping lxd juju controller"
/usr/bin/sg microk8s -c microk8s status --wait-ready
/usr/bin/sg microk8s -c juju bootstrap localhost localhost

echo "Deploying jenkins"
/usr/bin/sg microk8s -c python3 tests/integration/deploy_jenkins.py

echo "bootstraping microk8s juju controller"
/usr/bin/sg microk8s -c juju bootstrap microk8s micro
juju add-model testing -c micro
juju switch micro:admin/testing
sudo microk8s status --wait-ready
