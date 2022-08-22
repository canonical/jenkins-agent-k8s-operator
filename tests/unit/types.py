# Copyright 2022 Canonical Ltd.
# Licensed under the GPLv3, see LICENCE file for details.

import dataclasses


@dataclasses.dataclass
class CharmWithJenkinsRelation:
    """Data for charm with jenkins relation."""

    cpu_count: int
    machine_architecture: str
    remote_app: str
    remote_unit_name: str
    relation_id: int
