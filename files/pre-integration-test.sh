#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# lxd should be install and init by a previous step in integration test action.
juju bootstrap lxd localhost

pip3 install pyyaml
echo "Deploying jenkins"
python3 tests/integration/deploy_jenkins.py

# Integration test sometimes fails fails due to microk8s not setup and asked to run the following.
sudo usermod -a -G microk8s runner
sudo chown -f -R runner ~/.kube
newgrp microk8s
