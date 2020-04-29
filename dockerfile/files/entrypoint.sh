#!/bin/bash

set -eu -o pipefail

export LC_ALL=C

# defaults for jenkins-slave component of the jenkins continuous integration
# system

# location of java
typeset JAVA=/usr/bin/java

# arguments to pass to java - optional
# Just set this variable with whatever you want to add as an environment variable
# i.e JAVA_ARGS="-Xms 256m"
typeset JAVA_ARGS=${JAVA_ARGS:-""}

# URL of jenkins server to connect to
# Not specifying this parameter will stop the slave
# job from running.
typeset JENKINS_URL="${JENKINS_URL:?"URL of a jenkins server must be provided"}"

# Name of slave configuration to use at JENKINS_URL
# Override if it need to be something other than the
# hostname of the server the slave is running on.
typeset JENKINS_HOSTNAME="${JENKINS_HOSTNAME:-$(hostname)}"

# Arguments to pass to jenkins slave on startup
typeset -a JENKINS_ARGS

JENKINS_ARGS+=(-jnlpUrl "${JENKINS_URL}"/computer/"${JENKINS_HOSTNAME}"/slave-agent.jnlp)
JENKINS_ARGS+=(-jnlpCredentials "${JENKINS_API_USER:?Please specify JENKINS_API_USER}:${JENKINS_API_TOKEN:?Please specify JENKINS_API_TOKEN}")

# Path of the agent.jar
typeset AGENT_JAR=/var/lib/jenkins/agent.jar

download_agent() {
    ## Download the agent.jar

    # Retrieve Slave JAR from Master Server
    echo "Downloading agent.jar from ${JENKINS_URL}..."
    curl -L -s -o "${AGENT_JAR}".new "${JENKINS_URL}"/jnlpJars/agent.jar

    # Check to make sure slave.jar was downloaded.
    if [[ -s "${AGENT_JAR}".new ]]; then
        mv "${AGENT_JAR}".new "${AGENT_JAR}"
    else
        echo "Error while downloading ${AGENT_JAR}"
        exit 1
    fi
}

download_agent

# Specify the pod as ready
touch /var/lib/jenkins/slaves/.ready

#shellcheck disable=SC2086
"${JAVA}" ${JAVA_ARGS} -jar "${AGENT_JAR}"  "${JENKINS_ARGS[@]}"
