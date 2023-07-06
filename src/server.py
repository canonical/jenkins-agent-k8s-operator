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

logger = logging.getLogger(__name__)

JENKINS_WORKDIR = Path("/var/lib/jenkins")
AGENT_JAR_PATH = Path(JENKINS_WORKDIR / "agent.jar")
AGENT_READY_PATH = Path(JENKINS_WORKDIR / "agents/.ready")
ENTRYSCRIPT_PATH = Path(JENKINS_WORKDIR / "entrypoint.sh")

USER = "_daemon_"


class Credentials(BaseModel):
    """The credentials used to register to the Jenkins server.

    Attrs:
        address: The Jenkins server address to register to.
        secret: The secret used to register agent.
    """

    address: str
    secret: str


class ServerBaseError(Exception):
    """Represents errors with interacting with Jenkins server."""


class AgentJarDownloadError(ServerBaseError):
    """Represents an error downloading agent JAR executable."""


def download_jenkins_agent(server_url: str, container: ops.Container) -> None:
    """Download Jenkins agent JAR executable from server.

    Args:
        server_url: The Jenkins server URL address.
        container: The agent workload container.

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

    container.push(path=AGENT_JAR_PATH, make_dirs=True, source=res.content, user=USER)


def validate_credentials(
    agent_name: str,
    credentials: Credentials,
    container: ops.Container,
    add_random_delay: bool = False,
) -> bool:
    """Check if the credentials can be used to register to the server.

    Args:
        agent_name: The Jenkins agent name.
        credentials: Server credentials required to register to Jenkins server.
        container: The Jenkins agent workload container.
        add_random_delay: Whether random delay should be added to prevent parallel registration on
            server.

    Returns:
        True if credentials and agent_name pairs are valid, False otherwise.
    """
    # IMPORTANT: add random delay to prevent parallel execution.
    if add_random_delay:
        # It's okay to use random since it's not used for sensitive data.
        time.sleep(random.random())  # nosec
    proc: ops.pebble.ExecProcess = container.exec(
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
        working_dir=str(JENKINS_WORKDIR),
        combine_stderr=True,
    )
    # The process will exit due to connection failure(invalid credentials) or timeout.
    # Check for successful connection log from the stdout.
    connected = False
    terminated = False
    lines = ""
    # The proc.stdout is iterable according to process.exec documentation
    for line in proc.stdout:  # type: ignore
        lines += line
        if "INFO: Connected" in line:
            connected = True
        if "INFO: Terminated" in line:
            terminated = True
    logger.debug(lines)
    return connected and not terminated


def find_valid_credentials(
    agent_name_token_pairs: typing.Iterable[typing.Tuple[str, str]],
    server_url: str,
    container: ops.Container,
) -> typing.Optional[typing.Tuple[str, str]]:
    """Find credentials that can be applied if available.

    Args:
        agent_name_token_pairs: Matching agent name and token pair to check.
        server_url: The jenkins server url address.
        container: The Jenkins agent workload container.

    Returns:
        Agent name and token pair that can be used. None if no pair is available.
    """
    for agent_name, agent_token in agent_name_token_pairs:
        logger.debug("Validating %s", agent_name)
        if not validate_credentials(
            agent_name=agent_name,
            credentials=Credentials(address=server_url, secret=agent_token),
            container=container,
        ):
            logger.debug("agent %s validation failed.", agent_name)
            continue
        return (agent_name, agent_token)
    return None
