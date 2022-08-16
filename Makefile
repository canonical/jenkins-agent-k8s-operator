#!/usr/bin/make

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
project_dir := $(dir $(realpath $(mkfile_path)))
dockerfile_dir := $(project_dir)/dockerfile
charm_name := jenkins-agent-k8s

author ?= "Canonical IS team"
date_created ?= $(shell date +'%Y%m%d%H%M')

# Customize image name with environment variable
REVISION ?= $(shell git -C $(project_dir) rev-parse HEAD)
JENKINS_IMAGE ?= "localhost:32000/"$(charm_name):$(REVISION)

build-image: | $(dockerfile_dir)
	docker build \
	  --build-arg AUTHOR=$(author) \
	  --build-arg REVISION="$(revision)" \
	  -t $(JENKINS_IMAGE) $(dockerfile_dir)

build-image-no-cache: | $(dockerfile_dir)
	docker build \
	  --build-arg AUTHOR=$(author) \
	  --build-arg REVISION="$(revision)" \
	  --no-cache \
	  -t $(JENKINS_IMAGE) $(dockerfile_dir)

build-release-image: | $(dockerfile_dir)
	docker build \
	  --build-arg DATE_CREATED="$(date_created)" \
	  --build-arg AUTHOR=$(author) \
	  --build-arg REVISION="$(revision)" \
	  -t $(JENKINS_IMAGE) $(dockerfile_dir)

blacken:
	@echo "Normalising python layout with black."
	@tox -e black

lint: blacken
	@echo "Running flake8"
	@tox -e lint

# We actually use the build directory created by charmcraft,
# but the .charm file makes a much more convenient sentinel.
unittest: jenkins-agent.charm
	@tox -e unit

test: lint unittest

clean:
	@echo "Cleaning files"
	@git clean -fXd

jenkins-agent.charm: src/*.py requirements.txt
	charmcraft pack

.PHONY: lint test unittest clean
