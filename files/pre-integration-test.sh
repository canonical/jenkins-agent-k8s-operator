#!/bin/bash

pip3 install selenium pyyaml
echo "Deploying jenkins"
python3 tests/integration/deploy_jenkins.py