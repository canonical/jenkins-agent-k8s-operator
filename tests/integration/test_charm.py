#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from ops import model


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_blocked(app: model.Application):
    """
    arrange: given charm that has been built and deployed
    act: when the unit status is checked
    assert: then it is in the blocked state.
    """
    assert app.units[0].workload_status == model.BlockedStatus.name
