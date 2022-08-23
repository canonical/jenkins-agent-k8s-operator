# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from selenium.webdriver import FirefoxOptions, Firefox
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import subprocess
import yaml
import dataclasses
import logging
import sys

logging.basicConfig(
    stream=sys.stdout, format="%(levelname)s %(asctime)s - %(message)s", level=logging.INFO
)
LOGGER = logging.getLogger()


@dataclasses.dataclass
class JenkinsDeployment:
    """Key information about a jenkins deployment."""

    controller_name: str
    model_name: str
    unit_number: int
    public_address: str
    username: str
    password: str

    @property
    def hostname(self) -> str:
        """Calculate the hostname."""
        if ":" in self.public_address:
            return f"[{self.public_address}]"
        return self.public_address


def jenkins_active() -> bool:
    """Check whether the jenkins application is active."""
    result = subprocess.check_output(["juju", "status", "--format", "yaml"])
    return (
        yaml.safe_load(result)["applications"]["jenkins"]["application-status"]["current"]
        == "active"
    )


def deploy_jenkins() -> JenkinsDeployment:
    """Deploys jenkins to the lxd controller."""
    # Deploy
    LOGGER.info("deploying jenkins")
    controller_name = "lxd"
    model_name = "jenkins"
    subprocess.check_output(["juju", "switch", controller_name])
    # subprocess.check_output(["juju", "add-model", model_name, "localhost"])
    # subprocess.check_output(["juju", "deploy", "jenkins"])

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
    LOGGER.info("deployed jenkins: %s", deployment)
    return deployment


def set_agent_port_to_random(deployment: JenkinsDeployment):
    """Uses a browser to login and set the Jenkins agnt port to random."""
    LOGGER.info("configuring jenkins")

    LOGGER.info("starting browser")
    opts = FirefoxOptions()
    opts.add_argument("--headless")
    driver = Firefox(options=opts)

    # Login
    url = f"http://{deployment.hostname}:8080/login"
    LOGGER.info("logging into jenkins: %s", url)
    driver.get(url)
    time.sleep(1)
    elem = driver.find_element(By.NAME, "j_username")
    elem.send_keys(deployment.username)
    elem = driver.find_element(By.NAME, "j_password")
    elem.send_keys(deployment.password)
    elem.send_keys(Keys.RETURN)
    time.sleep(5)

    # Configure the port
    url = f"http://{deployment.hostname}:8080/configureSecurity/"
    LOGGER.info("configuring agent port: %s", url)
    driver.get(url)
    time.sleep(1)
    elem = driver.find_element(By.NAME, "slaveAgentPort")
    random_elem = elem.find_element(By.XPATH, "//*[text()='Random']")
    driver.execute_script("arguments[0].scrollIntoView();", elem)
    random_elem.click()
    elem = driver.find_element(By.XPATH, "//*[text()='Save']")
    elem.click()

    LOGGER.info("finished configuring jenkins")


def main():
    """Start jenkins and enable the agent port."""
    deployment = deploy_jenkins()
    print(deployment)
    set_agent_port_to_random(deployment=deployment)


if __name__ == "__main__":
    main()
