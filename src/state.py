# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The module for managing charm state."""

import logging
import os
import typing
from dataclasses import dataclass

import ops
from pydantic import BaseModel, Field, ValidationError

import metadata

# relation name used for compatibility with machine Jenkins server charm.
SLAVE_RELATION = "slave"
# agent relation name
AGENT_RELATION = "agent"

logger = logging.getLogger()


class CharmStateBaseError(Exception):
    """Represents error with charm state."""


class InvalidStateError(CharmStateBaseError):
    """Exception raised when state configuration is invalid."""

    def __init__(self, msg: str = ""):
        """Initialize a new instance of the InvalidStateError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


class JenkinsConfig(BaseModel):
    """The Jenkins config from juju config values.

    Attrs:
        server_url: The Jenkins server url.
        agent_names: Custom Jenkins agent names.
        agent_tokens: Tokens used to register Jenkins agent to Jenkins server.
    """

    server_url: str = Field(..., min_length=1)
    agent_names: typing.List[str] = Field(..., min_items=1)
    agent_tokens: typing.List[str] = Field(..., min_items=1)

    @classmethod
    def from_charm_config(cls, config: ops.ConfigData) -> typing.Optional["JenkinsConfig"]:
        """Instantiate JenkinsConfig from charm config.

        Args:
            config: Charm configuration data.

        Returns:
            JenkinsConfig if configuration exists, None otherwise.
        """
        server_url = config.get("jenkins_url", None)
        agent_names = config.get("jenkins_agent_name", None)
        agent_tokens = config.get("jenkins_agent_token", None)
        if not server_url and not agent_names and not agent_tokens:
            return None
        # type cast since Pydantic will throw validation error anyways.
        return cls(
            server_url=typing.cast(str, server_url),
            agent_names=typing.cast(str, agent_names).split(":"),
            agent_tokens=typing.cast(str, agent_tokens).split(":"),
        )


@dataclass
class State:
    """The k8s Jenkins agent state.

    Attrs:
        agent_meta: The Jenkins agent metadata to register on Jenkins server.
        jenkins_config: Jenkins configuration value from juju config.
        jenkins_agent_service_name: The Jenkins agent workload container name.
    """

    agent_meta: metadata.Agent
    jenkins_config: typing.Optional[JenkinsConfig]
    jenkins_agent_service_name: str = "jenkins-k8s-agent"

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "State":
        """Initialize the state from charm.

        Args:
            charm: The root k8s Jenkins agent charm.

        Raises:
            InvalidStateError: if invalid state values were encountered.

        Returns:
            Current state of k8s Jenkins agent.
        """
        try:
            agent_meta = metadata.Agent(
                num_executors=os.cpu_count() or 0,
                labels=charm.model.config.get("jenkins_agent_labels", "") or os.uname().machine,
                name=charm.unit.name.replace("/", "-"),
            )
        except ValidationError as exc:
            logging.error("Invalid executor state, %s", exc)
            raise InvalidStateError("Invalid executor state.") from exc

        try:
            jenkins_config = JenkinsConfig.from_charm_config(charm.config)
        except ValidationError as exc:
            logging.error("Invalid jenkins config values, %s", exc)
            raise InvalidStateError("Invalid jenkins config values.") from exc

        return cls(agent_meta=agent_meta, jenkins_config=jenkins_config)
