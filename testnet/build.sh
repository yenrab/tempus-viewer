#!/bin/sh
# Builds the slice from a clean state: the BEES natives (in a clone of project-bees), then the content node, the bridge and the
# reply check, each in its own directory under nodes/. Nothing in the user's own checkouts of BEES or Silica is written.
#
#   SILICA_COMPILER   the release compiler binary (required)
#   SILICA_ROOT       the public Silica repository checked out at the RELEASE commit (OI-18; never a local branch): its
#                     compiler/stdlib/*.silica and stdlib/net/silica_sockets.c are used. Cloned and checked out here when absent.
#   SILICA_COMMIT     the release commit (default e53689ec96c92699fc996a006762d40fcc288680, tag compiler-<that>)
#   BEES_ROOT         the clone of https://github.com/Silica-Language-and-Compiler/project-bees (cloned here when absent)
#   OPENSSL_PREFIX    OpenSSL 4.1 or later (BEES finds /opt/homebrew/opt/openssl by itself)
#   NAMES             the published names the nodes serve (default home)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
: "${SILICA_COMPILER:?set SILICA_COMPILER to the release compiler binary}"
: "${SILICA_ROOT:?set SILICA_ROOT to the clone of the Silica repository (a path that does not exist yet is cloned)}"
: "${SILICA_COMMIT:=e53689ec96c92699fc996a006762d40fcc288680}"
: "${BEES_ROOT:?set BEES_ROOT to the clone of project-bees (a path that does not exist yet is cloned)}"
export SILICA_ROOT BEES_ROOT NAMES="${NAMES:-home}"
[ -x "$SILICA_COMPILER" ] || { echo "no compiler at $SILICA_COMPILER"; exit 2; }
if [ ! -d "$SILICA_ROOT/.git" ]; then
    git clone -q https://github.com/Silica-Language-and-Compiler/silica "$SILICA_ROOT"
fi
git -C "$SILICA_ROOT" checkout -q "$SILICA_COMMIT"
[ "$(git -C "$SILICA_ROOT" rev-parse HEAD)" = "$SILICA_COMMIT" ] || { echo "SILICA_ROOT is not at $SILICA_COMMIT"; exit 2; }
echo "Silica at $(git -C "$SILICA_ROOT" log -1 --format='%h %ad' --date=short)"
[ -d "$SILICA_ROOT/compiler/stdlib" ] || { echo "no compiler/stdlib in $SILICA_ROOT"; exit 2; }
if [ ! -d "$BEES_ROOT/.git" ]; then
    git clone -q https://github.com/Silica-Language-and-Compiler/project-bees "$BEES_ROOT"
fi
echo "BEES at $(git -C "$BEES_ROOT" log -1 --format='%h %ad' --date=short)"
# BEES's native/dangerous_exposure_source/sockets is a relative link into a Silica checkout that sits beside the BEES one
sib="$(dirname "$BEES_ROOT")/silica"
[ "$sib" = "$SILICA_ROOT" ] || ln -sfn "$SILICA_ROOT" "$sib"
echo "$BEES_ROOT" > "$here/.bees_root"
# natives: `tls` first (tempus's rule names native/build/tls.flags, which only `tls` makes, so `tempus tls` in that order fails
# on a clean clone), then `tempus`, then `all` (the TRUST and socket archives the units link)
make -C "$BEES_ROOT/native" tls
make -C "$BEES_ROOT/native" tempus
# the sockets archive is made from SILICA_ROOT's silica_sockets.c: remake it when the source is newer or the root changed
rm -f "$BEES_ROOT/native/dangerous_exposure_source/lib/libsilica_sockets.a" "$BEES_ROOT/native/build/silica_sockets.o" 2>/dev/null || true
make -C "$BEES_ROOT/native" all
python3 "$BEES_ROOT/tools/bees_tempus_certs.py" check
make -C "$BEES_ROOT" check-compiler SILICA_COMPILER="$SILICA_COMPILER" || true
for leaf in content bridge replycheck; do
    make -C "$here/nodes/$leaf" clean-generated SILICA_COMPILER="$SILICA_COMPILER"
    start=$(date +%s)
    make -C "$here/nodes/$leaf" build SILICA_COMPILER="$SILICA_COMPILER"
    echo "[build.sh] $leaf: $(( $(date +%s) - start )) s"
done
