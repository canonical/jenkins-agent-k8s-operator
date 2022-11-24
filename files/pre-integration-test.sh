#!/bin/bash

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# lxd should be install and init by a previous step in integration test action.
juju bootstrap lxd local
pip3 install selenium pyyaml
echo "Deploying jenkins"
python3 tests/integration/deploy_jenkins.py