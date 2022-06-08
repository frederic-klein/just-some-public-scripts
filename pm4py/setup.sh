#!/bin/bash
sudo apt-get install -y jq
PM4PY_NAME='pm4py_docker'
FQDN="$1"
TENANT_ID=`cd /var/www/qwikis/core/tools/; sudo -u www-data ./tenant info ${FQDN} | jq -r '.id'`
WORKING_DIR="/var/www/qwikis/tenants/${TENANT_ID}/working/logs/"
PWD=$(pwd)
APT_PACKAGES='graphviz libgraphviz-dev pkg-config python3-pip'
PIP_PACKAGES='pygraphviz StrEnum'
INSTALL_DEPENDENCIES="apt-get update; apt-get install -y ${APT_PACKAGES}; pip install ${PIP_PACKAGES};"

sudo docker rm --force ${PM4PY_NAME}

sudo docker run -t --name ${PM4PY_NAME} --privileged --network=host pm4py/pm4py-core:latest bash -c "${INSTALL_DEPENDENCIES}";
sudo docker commit ${PM4PY_NAME} pm4py_complete
sudo docker rm --force ${PM4PY_NAME}

sudo docker run -d -t --name ${PM4PY_NAME} --mount type=bind,source=${WORKING_DIR},target=/promidigit/logs --mount type=bind,source=${PWD},target=/promidigit pm4py_complete sh;
