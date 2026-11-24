#!/bin/sh
# Brings the whole test network up on localhost, shows what runs, and stops it again. TEST network only.
#
#   testnet/network.sh start     starts every node (built by build.sh), waits until each is ready, prints the table
#   testnet/network.sh status    for each node: its process and whether its port is open (no connection is made to it)
#   testnet/network.sh stop      asks each node to end (the line `exit` on its standard input, as BEES's runners do), in the
#                                reverse order, waits for it, and only then (after 20 s) ends a node that did not leave
#
# Nodes, in the order they are started (a node that dials another comes after it):
#   authority  TRUST   24420   decides the marks, runs restart_node
#   content    TRUST   24400   home, status, directory, docs_*, gallery, image_part
#   data       TRUST   24410   nodes*, events, samples, search*, live, clock, slow, fail, empty
#   sentinel   TEMPUS  24430   the first sentinel: admits and samples, has no sentinel of its own
#   edge1..3   TEMPUS  24431..24433   edges that join through the sentinel
#   bridge     TEMPUS  24401   (its TRUST side 24406 is a client only: nothing listens) joins through the sentinel, routes calls
# Each node's own output goes to testnet/run/NAME.log, its process number to run/NAME.pid, and run/NAME.in is the named pipe
# that is its standard input. Needs the builds of build.sh and nothing else (no BEES_ROOT: every program is already linked).
# Exit status: start 0 when every node became ready (else everything started is stopped again and the status is 1);
# status 0 when every node runs and listens; stop 0 when no node process is left.
set -u
here=$(cd "$(dirname "$0")" && pwd)
run="$here/run"

# name:directory:program:port:line the node prints when it is ready
NODES="authority:authority:dangerous_authority:24420:listening on 127\\.0\\.0\\.1:24420
content:content:dangerous_content:24400:listening on 127\\.0\\.0\\.1:24400
data:data:dangerous_data:24410:listening on 127\\.0\\.0\\.1:24410
sentinel:tempus:dangerous_sentinel:24430:listening on 127\\.0\\.0\\.1:24430
edge1:tempus:dangerous_edge1:24431:^join: done\$
edge2:tempus:dangerous_edge2:24432:^join: done\$
edge3:tempus:dangerous_edge3:24433:^join: done\$
bridge:bridge:dangerous_bridge:24401:^join: done\$"

alive() { [ -f "$run/$1.pid" ] && kill -0 "$(cat "$run/$1.pid")" 2>/dev/null; }
listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
field() { echo "$1" | cut -d: -f"$2"; }

wait_ready() { # name pattern seconds
    t=0
    while [ "$t" -lt "$3" ]; do
        grep -E -q "$2" "$run/$1.log" 2>/dev/null && return 0
        alive "$1" || return 1
        sleep 1; t=$((t + 1))
    done
    return 1
}

stop_node() {
    n=$1
    if alive "$n"; then
        pid=$(cat "$run/$n.pid")
        # the process holds its own pipe open for reading and writing, so this write cannot block while it lives
        echo exit > "$run/$n.in"
        t=0
        while kill -0 "$pid" 2>/dev/null && [ "$t" -lt 20 ]; do sleep 1; t=$((t + 1)); done
        if kill -0 "$pid" 2>/dev/null; then
            echo "stop: $n did not leave in 20 s, ending it"; kill "$pid" 2>/dev/null; sleep 1
            kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
        fi
    fi
    rm -f "$run/$n.pid" "$run/$n.in"
}

do_stop() {
    rc=0
    for spec in $(echo "$NODES" | cut -d: -f1 | sed '1!G;h;$!d'); do stop_node "$spec"; done
    # nothing of ours may be left
    for spec in $(echo "$NODES" | cut -d: -f1); do
        if [ -f "$run/$spec.pid" ] || listening "$(field "$(echo "$NODES" | grep "^$spec:")" 4)"; then echo "stop: $spec is still there"; rc=1; fi
    done
    [ "$rc" = 0 ] && echo "network stopped"
    return $rc
}

do_status() {
    rc=0
    printf '%-10s %-7s %-6s %s\n' node process port state
    echo "$NODES" | while IFS= read -r spec; do
        n=$(field "$spec" 1); port=$(field "$spec" 4)
        if alive "$n"; then p="pid $(cat "$run/$n.pid")"; else p="-"; fi
        if listening "$port"; then l=open; else l=closed; fi
        printf '%-10s %-7s %-6s %s\n' "$n" "$p" "$port" "$l"
    done
    for spec in $(echo "$NODES" | cut -d: -f1); do
        alive "$spec" && listening "$(field "$(echo "$NODES" | grep "^$spec:")" 4)" || rc=1
    done
    return $rc
}

do_start() {
    mkdir -p "$run"
    for spec in $(echo "$NODES" | cut -d: -f1); do
        if alive "$spec"; then echo "start: $spec is already running (network.sh stop first)"; return 1; fi
    done
    echo "$NODES" | while IFS= read -r spec; do
        port=$(field "$spec" 4)
        if listening "$port"; then echo "start: port $port is in use by another process"; exit 1; fi
    done || return 1
    echo "$NODES" | while IFS= read -r spec; do
        n=$(field "$spec" 1); dir=$(field "$spec" 2); exe=$(field "$spec" 3); port=$(field "$spec" 4); pat=$(echo "$spec" | cut -d: -f5-)
        [ -x "$here/nodes/$dir/$exe" ] || { echo "start: $here/nodes/$dir/$exe is not built (testnet/build.sh)"; exit 1; }
        rm -f "$run/$n.in" "$run/$n.pid" "$run/tempus_checks.done"
        mkfifo "$run/$n.in" || exit 1
        # <> opens the pipe for reading and writing: the node never sees an end of file, and `exit` is written by stop
        (cd "$here/nodes/$dir" && nohup "./$exe" <> "$run/$n.in" > "$run/$n.log" 2>&1 & echo $! > "$run/$n.pid")
        if wait_ready "$n" "$pat" 60; then echo "up: $n (pid $(cat "$run/$n.pid"), port $port)"; else echo "start: $n did not become ready; see $run/$n.log"; exit 1; fi
    done
    rc=$?
    if [ "$rc" != 0 ]; then do_stop >/dev/null; return 1; fi
    echo; do_status
}

case "${1:-}" in
    start) do_start ;;
    stop) do_stop ;;
    status) do_status ;;
    *) echo "usage: $0 start|stop|status"; exit 2 ;;
esac
