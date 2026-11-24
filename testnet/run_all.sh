#!/bin/sh
# Calls every published name (and page, image part and mark) through the bridge and compares with data/out; see nodes/client/run_all.py.
# Starts the three TRUST nodes and the bridge built by build.sh and stops them. Needs BEES_ROOT (build.sh wrote .bees_root).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
: "${BEES_ROOT:=$(cat "$here/.bees_root" 2>/dev/null || true)}"
[ -n "$BEES_ROOT" ] || { echo "set BEES_ROOT (the project-bees clone build.sh used)"; exit 2; }
export BEES_ROOT
python3 "$here/data/gen.py" --check
python3 "$here/data/test_etf.py" | grep -c PASS | sed 's/^/test_etf.py: PASS lines: /'
python3 "$here/nodes/client/run_all.py" "$@"
rc=$?
python3 "$here/data/gen.py" --check
exit $rc
