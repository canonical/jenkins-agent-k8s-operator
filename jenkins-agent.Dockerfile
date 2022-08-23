ARG DIST_RELEASE=jammy
FROM ubuntu:${DIST_RELEASE}

ENTRYPOINT /entrypoint.sh

ARG DIST_RELEASE_VERSION=22.04

LABEL com.canonical.dist-release=${DIST_RELEASE}
LABEL com.canonical.dist-release-version=${DIST_RELEASE_VERSION}

ARG AUTHOR
LABEL org.opencontainers.image.authors=${OCI_AUTHOR}

LABEL org.opencontainers.image.url="https://launchpad.net/charm-k8s-jenkins-agent"
LABEL org.opencontainers.image.documentation="https://launchpad.net/charm-k8s-jenkins-agent"
LABEL org.opencontainers.image.source="https://launchpad.net/charm-k8s-jenkins-agent"
LABEL org.opencontainers.image.version="0.0.1"
LABEL org.opencontainers.image.vendor="Canonical"
LABEL org.opencontainers.image.licenses="Apache"

# Ensure that the needed directory are owned by the right user
ARG USER=jenkins
ARG USER_GID=999
ARG USER_UID=999
RUN mkdir /var/lib/jenkins \
	&& mkdir /var/lib/jenkins/agents \
	&& mkdir /var/log/jenkins \
	&& chown -Rh ${USER_UID}:${USER_GID} \
	/var/lib/jenkins \
	/var/lib/jenkins/agents \
	/var/log/jenkins \
	&& addgroup --gid ${USER_GID} ${USER} \
	&& adduser --system --uid ${USER_UID} --gid ${USER_GID} \
	--home /var/lib/jenkins --shell /bin/bash ${USER}

# Do not write on the overlay for the files located in this directory
VOLUME /var/lib/jenkins
VOLUME /var/lib/jenkins/agents
VOLUME /var/log/jenkins

# Install runtime requirements
RUN apt-get update -y \
	&& apt-get install -y \
	curl \
	default-jre-headless


WORKDIR /var/lib/jenkins

# Using root due to https://bugs.launchpad.net/juju/+bug/1879598
#USER ${USER}
USER root

COPY files/entrypoint.sh /

ARG DATE_CREATED=devel
LABEL org.opencontainers.image.created=${DATE_CREATED}

ARG REVISION=devel
LABEL org.opencontainers.image.revision=${REVISION}
