#!/bin/bash

GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

# if ! pgrep -f "vcxsrv.exe" > /dev/null; then
#     echo "🔁 Starting VcXsrv with no access control..."
#     /mnt/c/Program\ Files/VcXsrv/vcxsrv.exe :0 -multiwindow -clipboard -ac -silent-dup-error &
# fi

# export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0

source ../../venv/bin/activate

echo -e "${RED}Removing project files${RESET}"
rm project/c0000.xml
rm project/eventnameid.txt
rm project/statenameid.txt
rm project/c0000_cmsg.hks

echo -e "${YELLOW}Duplicating templates to project directory${RESET}"
cp template/c0000.xml project/c0000.xml
cp template/eventnameid.txt project/eventnameid.txt
cp template/statenameid.txt project/statenameid.txt
cp template/c0000_cmsg.hks project/c0000_cmsg.hks

echo -e "${GREEN}Running python script${RESET}"
python3 SDT-PC-BEH-Script.py
