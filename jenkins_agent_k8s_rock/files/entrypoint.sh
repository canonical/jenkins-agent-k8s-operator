#!/bin/bash

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

set -eu -o pipefail

export LC_ALL=C
export TERM=xterm

# defaults for jenkins-agent component of the jenkins continuous integration
# system

# location of java
typeset JAVA=/usr/bin/java


# URL of jenkins server to connect to
# Not specifying this parameter will stop the agent
# job from running.
typeset JENKINS_URL="${JENKINS_URL:?"URL of a jenkins server must be provided"}"
typeset JENKINS_AGENT="${JENKINS_AGENT:?"Jenkins agent name must be provided"}"
typeset JENKINS_TOKEN="${JENKINS_TOKEN:?"Jenkins agent token must be provided"}"

typeset JENKINS_HOME="/var/lib/jenkins"

# Ensure working directory is at $JENKINS_HOME
# -workDir parameter might be unreliable from experiences
# and jenkins can sometime ignore it (to be verified!)
cd $JENKINS_HOME
# Path of the agent.jar
typeset AGENT_JAR="${JENKINS_HOME}/agent.jar"

# Specify the pod as ready
touch "${JENKINS_HOME}/agents/.ready"

# Start Jenkins agent
echo "${JENKINS_AGENT}"
${JENKINS_HOME}/jenkins-agent -url "${JENKINS_URL}" -secret "${JENKINS_TOKEN}" -name ${JENKINS_AGENT} -noReconnect
# Remove ready mark if unsuccessful
rm ${JENKINS_HOME}/agents/.ready
