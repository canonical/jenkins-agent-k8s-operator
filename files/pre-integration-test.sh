#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# Jenkins charm is deployed on lxd and Jenkins agent charm is deployed on microk8s

# Enure setup of microk8s.
sudo microk8s status --wait-ready
sudo usermod -a -G microk8s "$USER"
sudo chown -f -R "$USER" ~/.kube
newgrp microk8s

microk8s kubectl -n kube-system rollout status -w deployment/hostpath-provisioner
microk8s kubectl -n kube-system rollout status -w deployment/coredns
microk8s kubectl -n container-registry rollout status -w deployment/registry
microk8s status --wait-ready

# lxd should be install and init by a previous step in integration test action.
echo "bootstraping lxd juju controller"
juju bootstrap localhost localhost

echo "Deploying jenkins"
python3 tests/integration/deploy_jenkins.py

echo "bootstraping microk8s juju controller"
newgrp microk8s
juju bootstrap microk8s micro
juju add-model testing -c micro
juju switch micro:admin/testing
sudo microk8s status --wait-ready

echo "Waiting until the outputs files exist"
until [ -f contorller_name.txt ]
do
     sleep 5
done
until [ -f model_name.txt ]
do
     sleep 5
done
until [ -f unit_number.txt ]
do
     sleep 5
done
echo "Output files found"