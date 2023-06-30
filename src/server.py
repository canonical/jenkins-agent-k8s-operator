# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Functions to interact with jenkins server."""

import logging
import random
import time
import typing
from pathlib import Path

import ops
import requests
from pydantic import BaseModel

import state

logger = logging.getLogger(__name__)

JENKINS_WORKDIR = Path("/var/lib/jenkins")
AGENT_JAR_PATH = Path(JENKINS_WORKDIR / "agent.jar")
AGENT_READY_PATH = Path(JENKINS_WORKDIR / "agents/.ready")
ENTRYSCRIPT_PATH = Path(JENKINS_WORKDIR / "entrypoint.sh")

USER = "jenkins"
GROUP = "jenkins"


class Credentials(BaseModel):
    """The credentials used to register to the Jenkins server.

    Attrs:
        address: The Jenkins server address to register to.
        secret: The secret used to register agent.
    """

    address: str
    secret: str

    @classmethod
    def from_jenkins_slave_interface_dict(
        cls, server_unit_databag: ops.RelationDataContent
    ) -> typing.Optional["Credentials"]:
        """Import server metadata from databag in slave relation.

        Args:
            server_unit_databag: The relation databag content from slave relation.

        Returns:
            Metadata if complete values(url, secret) are set. None otherwise.
        """
        address = server_unit_databag.get("url")
        secret = server_unit_databag.get("secret")
        if not address or not secret:
            return None
        return Credentials(address=address, secret=secret)

    @classmethod
    def from_jenkins_agent_v0_interface_dict(
        cls, server_unit_databag: ops.RelationDataContent, unit_name: str
    ) -> typing.Optional["Credentials"]:
        """Import server metadata from databag in agent relation.

        Args:
            server_unit_databag: The relation databag content from agent relation.
            unit_name: The agent unit name.

        Returns:
            Metadata if complete values(url, secret) are set. None otherwise.
        """
        address = server_unit_databag.get("url")
        secret = server_unit_databag.get(f"{unit_name}_secret")
        if not address or not secret:
            return None
        return Credentials(address=address, secret=secret)


def get_credentials(
    relation_name: str, unit_name: str, databag: typing.Optional[ops.RelationDataContent]
) -> typing.Optional["Credentials"]:
    """Get credentials from databag.

    Args:
        relation_name: The relation name of the databag. Either "slave" or "agent".
        unit_name: The agent unit name.
        databag: The relation databag for given relation.

    Returns:
        Credentials if databag contains valid metadata. None if partial or no metadata found.
    """
    if databag is None:
        return None
    if relation_name == state.SLAVE_RELATION:
        return Credentials.from_jenkins_slave_interface_dict(databag)
    return Credentials.from_jenkins_agent_v0_interface_dict(databag, unit_name=unit_name)


class ServerBaseError(Exception):
    """Represents errors with interacting with Jenkins server."""


class AgentJarDownloadError(ServerBaseError):
    """Represents an error downloading agent JAR executable."""


def download_jenkins_agent(server_url: str, connectable_container: ops.Container) -> None:
    """Download Jenkins agent JAR executable from server.

    Args:
        server_url: The Jenkins server URL address.
        connectable_container: The connectable agent container.

    Raises:
        AgentJarDownloadError: If an error occurred downloading the JAR executable.
    """
    try:
        res = requests.get(f"{server_url}/jnlpJars/agent.jar", timeout=300)
        res.raise_for_status()
    except (requests.HTTPError, requests.Timeout, requests.ConnectionError) as exc:
        logger.error("Failed to download agent JAR executable from server, %s", exc)
        raise AgentJarDownloadError(
            "Failed to download agent JAR executable from server."
        ) from exc

    connectable_container.push(
        path=AGENT_JAR_PATH, make_dirs=True, source=res.content, user=USER, group=GROUP
    )


def validate_credentials(
    agent_name: str, credentials: Credentials, connectable_container: ops.Container
) -> bool:
    """Check if the credentials can be used to register to the server.

    Args:
        agent_name: The Jenkins agent name.
        credentials: Server credentials required to register to Jenkins server.
        connectable_container: The Jenkins agent workload container.

    Returns:
        True if credentials and agent_name pairs are valid, False otherwise.
    """
    # IMPORTANT: add random jitter to prevent parallel execution.
    # It's okay to use random since it's not used for sensitive data.
    time.sleep(random.random())  # nosec
    proc: ops.pebble.ExecProcess = connectable_container.exec(
        [
            "java",
            "-jar",
            str(AGENT_JAR_PATH),
            "-jnlpUrl",
            f"{credentials.address}/computer/{agent_name}/slave-agent.jnlp",
            "-workDir",
            str(JENKINS_WORKDIR),
            "-noReconnect",
            "-secret",
            credentials.secret,
        ],
        timeout=5,
        user=USER,
        group=GROUP,
        working_dir=str(JENKINS_WORKDIR),
        combine_stderr=True,
    )
    # The process will exit due to connection failure(invalid credentials) or timeout.
    # Check for successful connection log from the stdout.
    connected = False
    terminated = False
    # The proc.stdout is iterable according to process.exec documentation
    for line in proc.stdout:  # type: ignore
        if "INFO: Connected" in line:
            connected = True
        if "INFO: Terminated" in line:
            terminated = True

    return connected and not terminated


def is_registered(connectable_container: ops.Container) -> bool:
    """Check if the given agent instance is already up and running.

    Args:
        connectable_container: The Jenkins agent workload container.

    Returns:
        Whether the Jenkins agent is already registered.
    """
    return connectable_container.exists(str(AGENT_READY_PATH))
