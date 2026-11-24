#!/bin/sh
# Runs the first slice: starts the content node and the bridge built by build.sh, has the client call viewer:home/0 through the
# bridge, compares the decoded reply with data/out/replies/home.etf and stops both. Needs BEES_ROOT (build.sh prints it; it
# defaults to the scratch clone of this session if that exists).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
: "${BEES_ROOT:=$(cat "$here/.bees_root" 2>/dev/null || true)}"
[ -n "$BEES_ROOT" ] || { echo "set BEES_ROOT (the project-bees clone build.sh used)"; exit 2; }
export BEES_ROOT
exec python3 "$here/nodes/client/run_slice.py" "$@"
