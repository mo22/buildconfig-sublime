#!/bin/bash
set -euo pipefail

if [ "$1" == "open" ]; then
    if screen -r "$2" -X info >/dev/null; then
        echo "session already exists" 1>&2
        exit 0
    fi
    screen -dmS "$2" sh -c "$3"

elif [ "$1" == "list" ]; then
    screen -ls | grep "^\t" | while read ID REST; do
        echo "$( echo "$ID" | cut -d . -f 1 )" "$( echo "$ID" | cut -d . -f 2- )"
    done

elif [ "$1" == "kill" ]; then
    if ! screen -r "$2" -X info >/dev/null; then
        # screen session does not exist
        exit 0
    fi
    screen -r "$2" -X quit

else
    echo "unknown command" 1>&2
    exit 1
fi
