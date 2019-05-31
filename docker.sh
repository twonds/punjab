#!/bin/bash
GIT_REV=$(git rev-parse HEAD)
docker build . -t twonds/punjab:${GIT_REV} -t twonds/punjab:latest

docker run --network host --rm twonds/punjab:latest run_tests.sh


