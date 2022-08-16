# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

import pytest_asyncio
import yaml
import pytest
from pytest_operator import plugin


@pytest.fixture(scope="module")
def metadata():
    """Provides charm metadata."""
    yield yaml.safe_load(Path("./metadata.yaml").read_text())


@pytest.fixture(scope="module")
def app_name(metadata):
    """Provides app name from the metadata."""
    yield metadata["name"]


@pytest_asyncio.fixture(scope="module")
async def app(ops_test: plugin.OpsTest, app_name: str, pytestconfig: pytest.Config):
    """Charm used for integration testing.
    Builds the charm and deploys it and the relations it depends on.
    """
    # Build and deploy the charm
    charm = await ops_test.build_charm(".")
    resources = {"jenkins-agent-image": pytestconfig.getoption("--jenkins-agent-image")}
    application = await ops_test.model.deploy(
        charm, resources=resources, application_name=app_name, series="jammy"
    )
    await ops_test.model.wait_for_idle()

    return application
