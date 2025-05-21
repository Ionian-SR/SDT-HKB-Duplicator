#!/bin/bash

GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

if ! pgrep -f "vcxsrv.exe" > /dev/null; then
    echo "🔁 Starting VcXsrv with no access control..."
    /mnt/c/Program\ Files/VcXsrv/vcxsrv.exe :0 -multiwindow -clipboard -ac -silent-dup-error &
fi

export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0

echo -e "${RED}Removing current c0000.xml${RESET}"
rm c0000.xml

echo -e "${YELLOW}Duplicating c0000_backup.xml to c0000.xml${RESET}"
cp c0000_backup.xml c0000.xml

echo -e "${GREEN}Running python script${RESET}"
python3 SDT-PC-BEH-Script.py
