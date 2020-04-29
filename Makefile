#!/usr/bin/make

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
project_dir := $(dir $(realpath $(mkfile_path)))
dockerfile_dir := $(project_dir)/dockerfile

author ?= "Canonical IS team"
revision ?= $(shell git -C $(project_dir) rev-parse HEAD)
date_created ?= $(shell date +'%Y%m%d')

build-image: | $(dockerfile_dir)
	docker build \
	  --build-arg DATE_CREATED="$(date_created)" \
	  --build-arg AUTHOR=$(author) \
	  --build-arg REVISION="$(revision)" \
	  -t jenkins-slave-operator:$(revision) $(dockerfile_dir)

build-image-dev: | $(dockerfile_dir)
	docker build -t jenkins-slave-operator:devel $(dockerfile_dir)
