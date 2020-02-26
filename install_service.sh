#!/bin/bash

set -e

wd="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo Working directory: ${wd}
echo XDG_RUNTIME_DIR: ${XDG_RUNTIME_DIR}
echo Parameters: ${@}

ewd=$(echo ${wd} | sed -e 's/[\/&]/\\&/g')
params=$(echo ${@} | sed -e 's/[\/&]/\\&/g')
xdg=$(echo ${XDG_RUNTIME_DIR} | sed -e 's/[\/&]/\\&/g')
cat ${wd}/demo.service.in |\
    sed "s/__WD__/${ewd}/g; s/__XDG__/${xdg}/g; s/__PARAMS__/${params}/g;" |\
    sudo tee /lib/systemd/system/demo.service > /dev/null

echo
echo Enabling service ...
sudo systemctl daemon-reload
sudo systemctl enable demo.service


enabled=$(sudo systemctl is-enabled demo)

echo Service status: ${enabled}
