# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The module for managing charm state."""

import logging
import os
import typing
from dataclasses import dataclass

import ops
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, tools

import metadata
import server

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
        server_url_not_validated: The Jenkins server url, to be validated with pydantic.
        server_url: The Jenkins server url, to be used by the charm.
        agent_name_token_pairs: Jenkins agent names paired with corresponding token value.
    """

    server_url_not_validated: AnyHttpUrl

    agent_name_token_pairs: typing.List[typing.Tuple[str, str]] = Field(..., min_items=1)

    @property
    def server_url(self) -> str:
        """Convert validated server_url to string."""
        return str(self.server_url_not_validated)

    @classmethod
    def from_charm_config(cls, config: ops.ConfigData) -> typing.Optional["JenkinsConfig"]:
        """Instantiate JenkinsConfig from charm config.

        Args:
            config: Charm configuration data.

        Returns:
            JenkinsConfig if configuration exists, None otherwise.
        """
        server_url = config.get("jenkins_url")
        agent_name_config = config.get("jenkins_agent_name")
        agent_token_config = config.get("jenkins_agent_token")
        # None represents an unset Jenkins configuration values, meaning configuration values from
        # relation would be used.
        if not server_url and not agent_name_config and not agent_token_config:
            return None
        agent_names = agent_name_config.split(":") if agent_name_config else []
        agent_tokens = agent_token_config.split(":") if agent_token_config else []
        agent_name_token_pairs = list(zip(agent_names, agent_tokens))
        return cls(
            server_url_not_validated=tools.parse_obj_as(AnyHttpUrl, server_url) or "",
            agent_name_token_pairs=agent_name_token_pairs,
        )


def _get_jenkins_unit(
    all_units: typing.Set[ops.Unit], current_app_name: str
) -> typing.Optional[ops.Unit]:
    """Get the Jenkins charm unit in a relation.

    Args:
        all_units: All units in a relation.
        current_app_name: The Jenkins-agent-k8s applictation name.

    Returns:
        The Jenkins server application unit in the relation if found. None otherwise.
    """
    for unit in all_units:
        # if the unit's application name is the same, this is peer unit. Otherwise, it is the
        # Jenkins server unit.
        if unit.app.name == current_app_name:
            continue
        return unit
    return None


def _get_credentials_from_slave_relation(
    server_unit_databag: ops.RelationDataContent,
) -> typing.Optional[server.Credentials]:
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
    return server.Credentials(address=address, secret=secret)


def _get_credentials_from_agent_relation(
    server_unit_databag: ops.RelationDataContent, unit_name: str
) -> typing.Optional[server.Credentials]:
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
    return server.Credentials(address=address, secret=secret)


@dataclass
class State:
    """The k8s Jenkins agent state.

    Attrs:
        agent_meta: The Jenkins agent metadata to register on Jenkins server.
        jenkins_config: Jenkins configuration value from juju config.
        slave_relation_credentials: The full set of credentials from the slave relation. None if
            partial data is set.
        agent_relation_credentials: The full set of credentials from the agent relation. None if
            partial data is set or the credentials do not belong to current agent.
        jenkins_agent_service_name: The Jenkins agent workload container name.
    """

    agent_meta: metadata.Agent
    jenkins_config: typing.Optional[JenkinsConfig]
    slave_relation_credentials: typing.Optional[server.Credentials]
    agent_relation_credentials: typing.Optional[server.Credentials]
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

        slave_relation = charm.model.get_relation(SLAVE_RELATION)
        slave_relation_credentials: typing.Optional[server.Credentials] = None
        if slave_relation and (
            slave_relation_jenkins_unit := _get_jenkins_unit(slave_relation.units, charm.app.name)
        ):
            slave_relation_credentials = _get_credentials_from_slave_relation(
                slave_relation.data[slave_relation_jenkins_unit]
            )
        agent_relation = charm.model.get_relation(AGENT_RELATION)
        agent_relation_credentials: typing.Optional[server.Credentials] = None
        if agent_relation and (
            agent_relation_jenkins_unit := _get_jenkins_unit(agent_relation.units, charm.app.name)
        ):
            agent_relation_credentials = _get_credentials_from_agent_relation(
                agent_relation.data[agent_relation_jenkins_unit], agent_meta.name
            )

        return cls(
            agent_meta=agent_meta,
            jenkins_config=jenkins_config,
            slave_relation_credentials=slave_relation_credentials,
            agent_relation_credentials=agent_relation_credentials,
        )
