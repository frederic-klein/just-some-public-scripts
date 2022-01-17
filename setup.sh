#!/bin/bash

PM4PY_NAME='pm4py_docker'
WORKING_DIR="$1"

sudo docker pull pm4py/pm4py-core:latest;
sudo docker run -d -t --name ${PM4PY_NAME} --mount type=bind,source=${WORKING_DIR},target=/promidigit pm4py/pm4py-core:latest
sudo docker exec ${PM4PY_NAME} bash -c 'apt-get install -y graphviz libgraphviz-dev pkg-config python3-pip; pip install pygraphviz;'
