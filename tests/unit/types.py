# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Useful types for testing."""

import dataclasses


@dataclasses.dataclass
class CharmWithJenkinsRelation:
    """Data for charm with jenkins relation.

    Attrs:
        cpu_count: Number of CPUs.
        machine_architecture: Machine architecture.
        remote_app: Remote app.
        remote_unit_name: Unit name.
        relation_id: Relation identifier.
    """

    cpu_count: int
    machine_architecture: str
    remote_app: str
    remote_unit_name: str
    relation_id: int
