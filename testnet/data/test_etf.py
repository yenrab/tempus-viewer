"""Checks the ETF writer against bytes that came from two other implementations:
the Silica encoder (testnet/experiments/etf-commands, run on the release compiler) and Erlang's term_to_binary."""
import subprocess, sys, os
from etf import Atom as A, enc, dec

# the bytes the Silica program printed for the three commands of cmds.silica (field order as declared there)
HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "..", "experiments", "etf-commands", "cmds_exe")
if os.path.exists(EXE):
    SILICA_HEX = subprocess.run([EXE], capture_output=True, text=True).stdout.split()[1]
else:
    SILICA_HEX = open(os.path.join(HERE, "silica_commands.hex")).read().strip()
term = [(A("heading"), {"into": "main", "level": 1, "text": "Nodes"}),
        (A("paragraph"), {"into": "main", "text": "Twelve nodes are up."}),
        (A("table_row"), {"into": "t1", "cells": ["n1", "up", "3"]})]
bad = 0
def norm(x):
    # text is written as a binary, so it reads back as bytes
    if isinstance(x, str) and not isinstance(x, A): return x.encode()
    if isinstance(x, tuple): return tuple(norm(i) for i in x)
    if isinstance(x, list): return [norm(i) for i in x]
    if isinstance(x, dict): return {k: norm(v) for k, v in x.items()}
    return x
def check(what, ok):
    global bad
    print(("PASS  " if ok else "FAIL  ") + what)
    bad += 0 if ok else 1

# map keys: Silica writes them in alphabetical order (cells before into), and so does the writer
check("the writer gives the bytes the Silica encoder gave", enc(term).hex() == SILICA_HEX)
check("the reader reads the Silica bytes back to the same term", dec(bytes.fromhex(SILICA_HEX)) == norm(term))
for n in (0, 255, 256, -1, 2**31 - 1, 2**31, -2**31 - 1, 2**64 + 5):
    check(f"integer {n} round trips", dec(enc(n)) == n)

# the same through Erlang, if it is installed
if subprocess.run(["which", "erl"], capture_output=True).returncode == 0:
    samples = [term, [], [[]], {"a": [1, 2, 3], "b": (A("x"), b"y")}, [2**40, -2**40, 70000]]
    for s in samples:
        hexd = enc(s).hex()
        out = subprocess.run(["erl", "-noshell", "-eval",
            f'B = binary:decode_hex(<<"{hexd}">>), io:format("~s", [binary:encode_hex(term_to_binary(binary_to_term(B)))]), halt().'],
            capture_output=True, text=True).stdout.strip().lower()
        # Erlang may write a map's keys in another order, so compare what each side reads, not the bytes
        out2 = subprocess.run(["erl", "-noshell", "-eval",
            f'B = binary:decode_hex(<<"{hexd}">>), T = binary_to_term(B), io:format("~s", [binary:encode_hex(term_to_binary(T, [{{minor_version, 2}}]))]), halt().'],
            capture_output=True, text=True).stdout.strip().lower()
        check(f"Erlang reads our bytes and writes bytes that decode to the same term: {str(s)[:40]}", dec(bytes.fromhex(out)) == norm(s) or dec(bytes.fromhex(out2)) == norm(s))
else:
    print("SKIP  Erlang is not installed")
sys.exit(1 if bad else 0)
