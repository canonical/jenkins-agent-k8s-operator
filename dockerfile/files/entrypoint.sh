#!/bin/bash

set -eu -o pipefail

export LC_ALL=C
export TERM=xterm

# defaults for jenkins-agent component of the jenkins continuous integration
# system

# location of java
typeset JAVA=/usr/bin/java

# arguments to pass to java - optional
# Just set this variable with whatever you want to add as an environment variable
# i.e JAVA_ARGS="-Xms 256m"
typeset JAVA_ARGS=${JAVA_ARGS:-""}

# URL of jenkins server to connect to
# Not specifying this parameter will stop the agent
# job from running.
typeset JENKINS_URL="${JENKINS_URL:?"URL of a jenkins server must be provided"}"

typeset JENKINS_WORKDIR="/var/lib/jenkins"

# Arguments to pass to jenkins agent on startup
typeset -a JENKINS_ARGS

# Path of the agent.jar
typeset AGENT_JAR=/var/lib/jenkins/agent.jar

download_agent() {
    ## Download the agent.jar

    # Retrieve agent JAR from Master Server
    echo "Downloading agent.jar from ${JENKINS_URL}..."
    curl -L -s -o "${AGENT_JAR}".new "${JENKINS_URL}"/jnlpJars/agent.jar

    # Check to make sure agent.jar was downloaded.
    if [[ -s "${AGENT_JAR}".new ]]; then
        mv "${AGENT_JAR}".new "${AGENT_JAR}"
    else
        echo "Error while downloading ${AGENT_JAR}"
        exit 1
    fi
}

download_agent

# Specify the pod as ready
touch /var/lib/jenkins/agents/.ready

shellcheck disable=SC2086

# Transform the env variables in arrays to iterate through it
IFS=':' read -r -a AGENTS <<< ${JENKINS_AGENTS}
IFS=':' read -r -a TOKENS <<< ${JENKINS_TOKENS}

echo ${!AGENTS[@]}

for index in ${!AGENTS[@]}; do
    echo "agent  : ${AGENTS[$index]}"
    echo "value: ${TOKENS[$index]}"
    echo "${JAVA}" "${JAVA_ARGS}" -jar "${AGENT_JAR}" -jnlpUrl "${JENKINS_URL}"/computer/"${AGENTS[$index]}"/slave-agent.jnlp -workDir "${JENKINS_WORKDIR}" -noReconnect -secret "${TOKENS[$index]}"
    ${JAVA} ${JAVA_ARGS} -jar ${AGENT_JAR} -jnlpUrl ${JENKINS_URL}/computer/${AGENTS[$index]}/slave-agent.jnlp -workDir ${JENKINS_WORKDIR} -noReconnect -secret ${TOKENS[$index]} || echo "Invalid or already used credentials."
done
