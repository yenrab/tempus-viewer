#!/bin/sh
# Builds the OI-13 spike: Silica program + C host + SwiftUI app, in one executable.
# SILICA_COMPILER: path to a compiler binary from the Silica releases.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
: "${SILICA_COMPILER:?set SILICA_COMPILER to the release compiler binary}"
cd "$here"
mkdir -p build silica/dangerous_exposure_source/lib silica/.trial_stdlib
# Support units the failure reporter needs (spike only; see README).
[ -f silica/.trial_stdlib/Supervisor.silica ] || cp "${SILICA_DIR:-$HOME/silica}/compiler/stdlib/Supervisor.silica" silica/.trial_stdlib/
[ -f silica/.trial_stdlib/trial_wait_int64.silica ] || cp "${SILICA_DIR:-$HOME/silica}/trials/lib_trial_support/trial_wait_int64.silica" silica/.trial_stdlib/
clang -O2 -mmacosx-version-min=26.0 -c host/viewer_host.c -o build/viewer_host.o
ar rcs silica/dangerous_exposure_source/lib/libviewer_host.a build/viewer_host.o
printf 'dangerous_viewer_spike.silica\n.trial_stdlib/Supervisor.silica\n.trial_stdlib/trial_wait_int64.silica\n' > silica/silica.config
(cd silica && "$SILICA_COMPILER" > ../build/compile.log 2>&1 && grep -q "Compilation complete" ../build/compile.log) || { tail -30 build/compile.log; exit 1; }
for f in silica/__silica_runtime silica/dangerous_viewer_spike silica/.trial_stdlib/Supervisor silica/.trial_stdlib/trial_wait_int64; do
  clang -mmacosx-version-min=26.0 -c -x assembler "$f.sams" -o "build/$(basename "$f").o"
done
swiftc -O -parse-as-library -import-objc-header host/viewer_host.h app/App.swift \
  build/__silica_runtime.o build/dangerous_viewer_spike.o build/Supervisor.o build/trial_wait_int64.o \
  silica/dangerous_exposure_source/lib/libviewer_host.a -o spike
echo "built $here/spike"
