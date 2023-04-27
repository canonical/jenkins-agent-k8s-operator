# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Deploy jenkins to lxd using juju."""

import dataclasses
import logging
import subprocess
import sys
import time

import yaml

logging.basicConfig(
    stream=sys.stdout, format="%(levelname)s %(asctime)s - %(message)s", level=logging.INFO
)
LOGGER = logging.getLogger()


@dataclasses.dataclass
class JenkinsDeployment:
    """Key information about a jenkins deployment.

    Attrs:
        controller_name: Controller name.
        model_name: Model name.
        unit_number: Unit number.
        public_address: Public address.
        username: Username.
        password: Password.
        hostname: Hostname.
    """

    controller_name: str
    model_name: str
    unit_number: int
    public_address: str
    username: str
    password: str

    @property
    def hostname(self) -> str:
        """Calculate the hostname.

        Returns:
            The hostname.
        """
        if ":" in self.public_address:
            return f"[{self.public_address}]"
        return self.public_address


def jenkins_active() -> bool:
    """Check whether the jenkins application is active.

    Returns:
        True if Jenkins is active.
    """
    result = subprocess.check_output(["juju", "status"])
    LOGGER.info("juju status \n%s", result.decode("utf-8"))
    result = subprocess.check_output(["juju", "status", "--format", "yaml"])
    return (
        yaml.safe_load(result)["applications"]["jenkins"]["application-status"]["current"]
        == "active"
    )


def deploy_jenkins() -> JenkinsDeployment:
    """Deploys jenkins to the lxd controller.

    Returns:
        Jenkins deployment details.
    """
    # Deploy
    LOGGER.info("deploying jenkins")
    result = subprocess.check_output(["juju", "controllers", "--format", "yaml"])
    controller_name = next(
        filter(
            lambda item: item[1]["cloud"] == "localhost",
            yaml.safe_load(result)["controllers"].items(),
        )
    )[0]
    model_name = "jenkins"
    subprocess.check_output(["juju", "switch", controller_name])
    subprocess.check_output(["juju", "add-model", model_name, "localhost"])
    subprocess.check_output(["juju", "deploy", "jenkins", "--series", "focal"])

    # Wait for it to be active
    LOGGER.info("waiting for jenkins to become active")
    for _ in range(100):
        time.sleep(10)
        if jenkins_active():
            break
    assert jenkins_active(), "jenkins did not become active"

    # Get unit number, public address and username and password
    result = subprocess.check_output(["juju", "status", "--format", "yaml"])
    unit_number = int(next(iter(yaml.safe_load(result)["machines"].keys())))
    result = subprocess.check_output(
        [
            "juju",
            "run-action",
            f"jenkins/{unit_number}",
            "get-admin-credentials",
            "--wait",
            "--format",
            "yaml",
        ]
    )
    result_dict = yaml.safe_load(result)[f"unit-jenkins-{unit_number}"]["results"]
    username = result_dict["username"]
    password = result_dict["password"]
    result = subprocess.check_output(
        ["juju", "show-unit", f"jenkins/{unit_number}", "--format", "yaml"]
    )
    public_address = yaml.safe_load(result)[f"jenkins/{unit_number}"]["public-address"]

    deployment = JenkinsDeployment(
        controller_name=controller_name,
        model_name=model_name,
        unit_number=unit_number,
        public_address=public_address,
        username=username,
        password=password,
    )
    LOGGER.info("deployed jenkins")
    return deployment


def main():
    """Start jenkins and enable the agent port."""
    deployment = deploy_jenkins()

    # Writing output parameters to files
    with open(file="controller_name.txt", mode="w", encoding="utf-8") as text_file:
        text_file.write(deployment.controller_name)
    with open(file="model_name.txt", mode="w", encoding="utf-8") as text_file:
        text_file.write(deployment.model_name)
    with open(file="unit_number.txt", mode="w", encoding="utf-8") as text_file:
        text_file.write(str(deployment.unit_number))


if __name__ == "__main__":
    main()
