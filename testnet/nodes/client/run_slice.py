#!/usr/bin/env python3
"""Starts the content node and the bridge (the programs `testnet/build.sh` built), runs the client, stops both.

    BEES_ROOT=... python3 run_slice.py [--name home]

Each program runs in its own directory (it reads its files from there), stdout through a pty as BEES's trial runner does;
their output goes to testnet/run/content.log and bridge.log. Ports: content TRUST 24400, bridge TEMPUS 24401 (the viewer will
use 481 later), the bridge's own TRUST port 24406 (configured, nothing listens). Exit status is the client's."""
import argparse, os, pty, re, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTNET = os.path.abspath(os.path.join(HERE, "..", ".."))
RUN = os.path.join(TESTNET, "run")
sys.path.insert(0, HERE)
import call_home  # noqa: E402


class Node:
    def __init__(self, leaf, exe, log):
        master, slave = pty.openpty()
        self.log, self.chunks, self.cv = log, [], threading.Condition()
        self.proc = subprocess.Popen([os.path.join(leaf, exe)], cwd=leaf, stdin=subprocess.PIPE, stdout=slave,
                                     stderr=subprocess.PIPE, close_fds=True)
        os.close(slave)
        self.master = master
        self.t1 = threading.Thread(target=self._pump_out, daemon=True); self.t1.start()
        self.t2 = threading.Thread(target=self._pump_err, daemon=True); self.t2.start()

    def _add(self, data):
        with self.cv:
            self.chunks.append(data); self.cv.notify_all()

    def _pump_out(self):
        while True:
            try:
                d = os.read(self.master, 65536)
            except OSError:
                return
            if not d:
                return
            self._add(d)

    def _pump_err(self):
        while True:
            d = self.proc.stderr.read1(65536)
            if not d:
                return
            self._add(b"[stderr] " + d)

    def text(self):
        return b"".join(self.chunks).replace(b"\r\n", b"\n").decode("utf-8", "replace")

    def wait(self, pattern, timeout=30.0):
        rx, until = re.compile(pattern, re.M), time.monotonic() + timeout
        with self.cv:
            while not rx.search(self.text()):
                left = until - time.monotonic()
                if left <= 0 or self.proc.poll() is not None:
                    raise SystemExit("FAIL: %s did not print /%s/; its output:\n%s" % (self.log, pattern, self.text()))
                self.cv.wait(min(left, 0.2))

    def stop(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write(b"exit\n"); self.proc.stdin.flush()
            except Exception:
                pass
        try:
            rc = self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill(); rc = self.proc.wait(); self.chunks.append(b"\n[run_slice] killed\n")
        time.sleep(0.3)
        with open(self.log, "w") as f:
            f.write(self.text()); f.write("exit=%d\n" % rc)
        return rc


def reply_check(name):
    """no network: the content node's own generated entry for viewer:NAME/0, run by nodes/replycheck, against the reference"""
    leaf = os.path.join(TESTNET, "nodes", "replycheck")
    out = subprocess.run([os.path.join(leaf, "replycheck")], cwd=leaf, capture_output=True, text=True, timeout=60).stdout
    m = re.search(r"^etf ([0-9a-f]*)$", out, re.M)
    ref = open(os.path.join(TESTNET, "data", "out", "replies", name + ".etf"), "rb").read()
    same = bool(m) and bytes.fromhex(m.group(1)) == ref[1:]
    print("reply check (no network): the content node's computed bytes equal %s.etf (%d bytes, version byte aside): %s" % (name, len(ref), "YES" if same else "NO"))
    return same


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument("--name", default="home"); a = ap.parse_args(argv)
    os.makedirs(RUN, exist_ok=True)
    reply_check(a.name)
    content = bridge = None
    try:
        content = Node(os.path.join(TESTNET, "nodes", "content"), "dangerous_content", os.path.join(RUN, "content.log"))
        content.wait(r"listening on 127\.0\.0\.1")
        bridge = Node(os.path.join(TESTNET, "nodes", "bridge"), "dangerous_bridge", os.path.join(RUN, "bridge.log"))
        bridge.wait(r"tempus_bridge node \S+ listening on 127\.0\.0\.1:24401")  # its sentinel (network.sh) need not be there: the join retries
        rc = call_home.main(["--name", a.name])
        time.sleep(0.5)
    finally:
        for n in (bridge, content):
            if n:
                print("%s exit=%s" % (os.path.basename(n.log), n.stop()))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
