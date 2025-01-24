# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The module for handling agent metadata."""

import typing

from pydantic import BaseModel, Field


class Agent(BaseModel):
    """The Jenkins agent metadata.

    Attrs:
        num_executors: The number of executors available on the unit.
        labels: The comma separated labels to assign to the agent.
        name: The name of the agent.
    """

    num_executors: int = Field(..., ge=1)
    labels: str
    name: str

    def get_jenkins_agent_v0_interface_dict(self) -> typing.Dict[str, str]:
        """Generate dictionary representation of agent metadata.

        Returns:
            A dictionary adhering to jenkins_agent_v0 interface.
        """
        return {
            "executors": str(self.num_executors),
            "labels": self.labels,
            "name": self.name,
        }
