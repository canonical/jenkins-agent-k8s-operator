#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# Enure setup of microk8s.
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube
newgrp microk8s

# lxd should be install and init by a previous step in integration test action.
juju bootstrap localhost localhost

echo "Deploying jenkins"
python3 tests/integration/deploy_jenkins.py
