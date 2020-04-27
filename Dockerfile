ARG DIST_RELEASE=focal
FROM ubuntu:${DIST_RELEASE}

ARG DIST_RELEASE_VERSION=20.04

LABEL com.canonical.dist-release=${DIST_RELEASE}
LABEL com.canonical.dist-release=${DIST_RELEASE_VERSION}


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
		default-jre-headless \
		wget

WORKDIR /var/lib/jenkins
USER ${USER}
