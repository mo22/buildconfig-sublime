#!/bin/bash
set -euo pipefail

if [ "$1" == "open" ]; then
    PIDFILE="$TMPDIR/background-process.$2.pid"
    if [ -e "$PIDFILE" ]; then
        if kill -0 "$( cat "$PIDFILE" )" 2>/dev/null; then
            echo "session already exists" 1>&2
            exit 0
        fi
    fi
    CMDFILE="$TMPDIR/$$.command"
    echo 'echo -en "\033]0;'"$2"'\a"' >> $CMDFILE
    echo "rm $CMDFILE" > $CMDFILE
    echo 'trap "/bin/rm -f '$PIDFILE'" INT TERM EXIT' >> $CMDFILE
    echo 'echo $$ > '$PIDFILE >> $CMDFILE
    echo "$3" >> $CMDFILE
    chmod +x $CMDFILE
    open $CMDFILE

elif [ "$1" == "list" ]; then
    for I in "$TMPDIR/background-process."*.pid; do
        [ -e "$I" ] || continue;
        if ! kill -0 "$( cat "$I" )" 2>/dev/null; then
            rm "$I"
        else
            echo "$( cat "$I" ) $( basename "$I" | cut -d . -f 2- | sed -e 's/\.pid$//' )"
        fi
    done

elif [ "$1" == "kill" ]; then
    PIDFILE="$TMPDIR/background-process.$2.pid"
    if ! [ -e "$PIDFILE" ]; then
        # session does not exist
        exit 0
    fi
    if ! kill -0 "$( cat "$PIDFILE" )" 2>/dev/null; then
        rm "$PIDFILE"
    else
        echo "using pkill"
        pkill -0 -P "$( cat "$PIDFILE" )" -l
        pkill -9 -P "$( cat "$PIDFILE" )" -l
        # for (( I=0; I<20; I++ )); do
        #     sleep 0.2
        #     kill -0 "$( cat "$PIDFILE" )" 2>/dev/null || break
        # done
        # if kill -0 "$( cat "$PIDFILE" )" 2>/dev/null; then
        #     echo "kill $( cat "$PIDFILE" ) please"
        #     # pkill -9 -P "$( cat "$PIDFILE" )"
        #     sleep 0.5
        # fi
    fi

else
    echo "unknown command" 1>&2
    exit 1
fi
