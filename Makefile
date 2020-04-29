#!/usr/bin/make

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
project_dir := $(dir $(realpath $(mkfile_path)))
dockerfile_dir := $(project_dir)/dockerfile
charm_name := jenkins-slave-k8s

author ?= "Canonical IS team"
date_created ?= $(shell date +'%Y%m%d%H%M')

# Customize image name with environment variable
REVISION ?= $(shell git -C $(project_dir) rev-parse HEAD)
JENKINS_IMAGE ?= $(charm_name):$(REVISION)

build-image: | $(dockerfile_dir)
	docker build \
	  --build-arg AUTHOR=$(author) \
	  --build-arg REVISION="$(revision)" \
	  -t $(JENKINS_IMAGE) $(dockerfile_dir)

build-release-image: | $(dockerfile_dir)
	docker build \
	  --build-arg DATE_CREATED="$(date_created)" \
	  --build-arg AUTHOR=$(author) \
	  --build-arg REVISION="$(revision)" \
	  -t $(JENKINS_IMAGE) $(dockerfile_dir)
