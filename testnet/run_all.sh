#!/bin/sh
# Starts the whole network (network.sh start), calls every published name (and page, image part and mark) through the bridge and
# compares with data/out (nodes/client/run_all.py), checks that each TEMPUS node is up and does its role
# (nodes/client/run_tempus.py), and stops the network again, whatever happened. Needs the builds of build.sh and BEES_ROOT
# (build.sh wrote .bees_root). With --keep the network is left running (stop it with network.sh stop).
set -u
here=$(cd "$(dirname "$0")" && pwd)
: "${BEES_ROOT:=$(cat "$here/.bees_root" 2>/dev/null || true)}"
[ -n "$BEES_ROOT" ] || { echo "set BEES_ROOT (the project-bees clone build.sh used)"; exit 2; }
export BEES_ROOT
keep=0
[ "${1:-}" = "--keep" ] && keep=1
python3 "$here/data/gen.py" --check || exit 1
python3 "$here/data/test_etf.py" | grep -c PASS | sed 's/^/test_etf.py: PASS lines: /'
if ! "$here/network.sh" start; then exit 1; fi
if [ "$keep" = 0 ]; then trap '"$here/network.sh" stop' EXIT INT TERM; fi
python3 "$here/nodes/client/run_all.py"
rc1=$?
python3 "$here/nodes/client/run_tempus.py"
rc2=$?
python3 "$here/data/gen.py" --check
rc3=$?
[ "$rc1" = 0 ] && [ "$rc2" = 0 ] && [ "$rc3" = 0 ]
