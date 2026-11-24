#!/bin/sh
# Builds and runs the command-list encoding experiment with a release compiler.
# SILICA_COMPILER: a compiler binary from the Silica releases. SILICA_DIR: the Silica checkout (for wire_etf.silica:
# the release compiler does not carry the standard library units, so their sources must come from a checkout).
set -eu
cd "$(dirname "$0")"
: "${SILICA_COMPILER:?set SILICA_COMPILER}"
ln -sf "${SILICA_DIR:-$HOME/silica}/compiler/stdlib/wire_etf.silica" wire_etf.silica
printf 'cmds.silica\nwire_etf.silica\n' > silica.config
"$SILICA_COMPILER" > compile.log 2>&1 && grep -q "Compilation complete" compile.log || { tail -20 compile.log; exit 1; }
for f in cmds wire_etf __silica_runtime; do clang -mmacosx-version-min=26.0 -c -x assembler "$f.sams" -o "$f.o"; done
clang cmds.o wire_etf.o __silica_runtime.o -o cmds_exe -Wl,-e,main -Wl,-macos_version_min,26.0
./cmds_exe
