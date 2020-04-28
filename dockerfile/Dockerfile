ARG DIST_RELEASE=focal
FROM ubuntu:${DIST_RELEASE}

ENTRYPOINT /entrypoint.sh

ARG DIST_RELEASE_VERSION=20.04

LABEL com.canonical.dist-release=${DIST_RELEASE}
LABEL com.canonical.dist-release=${DIST_RELEASE_VERSION}

ARG AUTHOR
LABEL org.opencontainers.image.authors=${OCI_AUTHOR}

LABEL org.opencontainers.image.url="https://github.com/canonical/jenkins-slave-operator"
LABEL org.opencontainers.image.documentation="https://github.com/canonical/jenkins-slave-operator"
LABEL org.opencontainers.image.source="https://github.com/canonical/jenkins-slave-operator"
LABEL org.opencontainers.image.version="0.0.1"
LABEL org.opencontainers.image.vendor="Canonical"
LABEL org.opencontainers.image.licenses="Apache"

# Ensure that the needed directory are owned by the right user
ARG USER=jenkins
ARG USER_GID=999
ARG USER_UID=999
RUN mkdir /var/lib/jenkins \
	&& mkdir /var/lib/jenkins/slaves \
	&& mkdir /var/log/jenkins \
	&& chown -Rh ${USER_UID}:${USER_GID} \
		/var/lib/jenkins \
		/var/lib/jenkins/slaves \
		/var/log/jenkins \
	&& addgroup --gid ${USER_GID} ${USER} \
	&& adduser --system --uid ${USER_UID} --gid ${USER_GID} \
		--home /var/lib/jenkins --shell /bin/bash ${USER}

# Do not write on the overlay for the files located in this directory
VOLUME /var/lib/jenkins
VOLUME /var/lib/jenkins/slaves
VOLUME /var/log/jenkins

# Install runtime requirements
RUN apt-get update -y \
	&& apt-get install -y \
		curl \
		default-jre-headless


WORKDIR /var/lib/jenkins

USER ${USER}

COPY files/entrypoint.sh /

ARG DATE_CREATED=devel
LABEL org.opencontainers.image.created=${DATE_CREATED}

ARG REVISION=devel
LABEL org.opencontainers.image.revision=${REVISION}
