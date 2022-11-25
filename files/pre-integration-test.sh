#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# lxd should be install and init by a previous step in integration test action.
juju bootstrap lxd localhost

# Ensure microk8s is setup correctly
sudo microk8s status --wait-ready
sudo microk8s enable dns hostpath-storage registry
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube

# Ensure the features are ready
sudo microk8s.kubectl -n kube-system rollout status -w deployment/hostpath-provisioner
sudo microk8s.kubectl -n kube-system rollout status -w deployment/coredns
sudo microk8s.kubectl -n container-registry rollout status -w deployment/registry

# Bootstrap a juju controller on microk8s
sg microk8s -c "juju bootstrap microk8s micro"
juju switch micro

pip3 install pyyaml python3.10
echo "Deploying jenkins"
python3 tests/integration/deploy_jenkins.py
