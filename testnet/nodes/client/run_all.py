#!/usr/bin/env python3
"""Starts the three TRUST nodes and the bridge, calls every name through the bridge and compares with the reference data.

    BEES_ROOT=... python3 run_all.py [--keep-going]

For every name and page: the decoded value must equal the term of data/out/replies/NAME[.N].etf and the reference bytes
(without the version byte) must appear verbatim inside the result frame. For every name viewer:mark is called and compared with
data/out/index.json. image_part is compared with the bytes of data/out/images/*.png. fail, empty, slow and an unexported name
are checked as stated in the report. Prints a table; exit status 0 only when nothing failed. The BEES Python client reads no
tuples (its docstring says so), so a reply arrives as "refused ... bad_tag" with the frame in out.body; we read the frame with
the testnet's own reader (data/etf.py). TEST network only."""
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTNET = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(TESTNET, "data"))
import call_home  # noqa: E402
import etf  # noqa: E402
from run_slice import Node  # noqa: E402

RUN = os.path.join(TESTNET, "run")
REPLIES = os.path.join(TESTNET, "data", "out", "replies")
IMAGES = os.path.join(TESTNET, "data", "out", "images")
INDEX = json.load(open(os.path.join(TESTNET, "data", "out", "index.json")))
ADDR = "127.0.0.1:24401"
PART_MAX = 131000                       # the largest image part that fits one frame (131072) with the frames' own bytes
SLOW_MIN, SLOW_MAX = 0.8, 3.0           # seconds: slow's delay is above the first and below the bridge's call timeout (3 s TRUST, 4 s TEMPUS)
rows = []                               # (group, label, ok, detail)
_n = [0]


def ref(name):
    return open(os.path.join(REPLIES, name + ".etf"), "rb").read()


def fetch(name, args=()):
    """-> (value or None, raw frame body, outcome line, seconds)"""
    _n[0] += 1
    t = time.time()
    out = call_home.call(ADDR, name, args, req_id="r%d" % _n[0])
    dt = time.time() - t
    time.sleep(0.12)
    frame = None
    if out.body:
        try:
            frame = etf.dec(out.body)
        except Exception:
            frame = None
    if isinstance(frame, dict) and str(frame.get("t")) == "result" and "value" in frame:
        return frame["value"], out.body, out.line()[:120], dt
    return None, out.body, out.line()[:160], dt


def record(group, label, ok, detail=""):
    rows.append((group, label, bool(ok), detail))


def check_reply(group, label, name, args, ref_name):
    v, body, line, _ = fetch(name, args)
    if v is None:
        record(group, label, False, "no result: " + line)
        return
    r = ref(ref_name)
    eq = v == etf.dec(r)
    verbatim = r[1:] in body
    record(group, label, eq and verbatim, "decoded %s, verbatim bytes %s, %d bytes" % ("equal" if eq else "DIFFERENT", "yes" if verbatim else "NO", len(r)))


def main(argv):
    os.makedirs(RUN, exist_ok=True)
    nodes = {}
    try:
        for n, port in (("content", 24400), ("data", 24410), ("authority", 24420)):
            nodes[n] = Node(os.path.join(TESTNET, "nodes", n), "dangerous_" + n, os.path.join(RUN, n + ".log"))
            nodes[n].wait(r"listening on 127\.0\.0\.1:%d" % port)
        nodes["bridge"] = Node(os.path.join(TESTNET, "nodes", "bridge"), "dangerous_bridge", os.path.join(RUN, "bridge.log"))
        nodes["bridge"].wait(r"^join: no sentinel is configured$")
        run_checks()
    finally:
        for n in ("bridge", "authority", "data", "content"):
            if n in nodes:
                print("%s.log exit=%s" % (n, nodes[n].stop()))
    return report()


def run_checks():
    # ---- names with no arguments, and the ones with fixed arguments
    for name in ("home", "status", "directory", "docs_intro", "docs_commands", "gallery", "nodes", "nodes_summary", "search", "live", "empty"):
        check_reply("names", name, name, [], name)
    check_reply("names", "nodes_table", "nodes_table", ["1"], "nodes_table")
    check_reply("names", "node", "node", ["n01"], "node")
    check_reply("names", "search_results", "search_results", ["q", "test", "scope", "all", "exact", "false"], "search_results")
    check_reply("names", "clock(0)", "clock", ["0"], "clock")
    check_reply("names", "clock(1)", "clock", ["1"], "clock")
    check_reply("names", "restart_node", "restart_node", ["n01"], "restart_node")
    # ---- pages
    for p in range(1, 21):
        check_reply("events", "events page %d" % p, "events", [str(p)], "events.%d" % p)
    check_reply("events", "events (the name itself = page 1)", "events", ["1"], "events")
    check_reply("samples", "samples (the frame, no arguments)", "samples", [], "samples")
    for p in range(1, 21):
        check_reply("samples", "samples page %d" % p, "samples", [str(p)], "samples.%d" % p)
    # ---- images
    for k, b in (("icon", open(os.path.join(IMAGES, "icon.png"), "rb").read()), ("chart", open(os.path.join(IMAGES, "chart.png"), "rb").read()),
                 ("photo", open(os.path.join(IMAGES, "photo.png"), "rb").read())):
        parts = [(i, min(PART_MAX, len(b) - i)) for i in range(0, len(b), PART_MAX)]
        got = b""
        ok = True
        for off, ln in parts:
            v, body, line, _ = fetch("image_part", [k, str(off), str(ln)])
            if v is None or v != b[off:off + ln]:
                ok = False
                record("images", "image_part %s %d+%d" % (k, off, ln), False, "no result or bytes differ: " + line)
                break
            got += v
            record("images", "image_part %s offset %d length %d" % (k, off, ln), b[off:off + ln] in body, "bytes equal the PNG's, verbatim in the frame")
        if ok:
            record("images", "image %s reassembled (%d parts)" % (k, len(parts)), got == b, "%d bytes" % len(b))
    v, body, line, _ = fetch("image_part", ["photo", "0", "131072"])
    record("images", "image_part photo 0+131072 (over the frame ceiling)", v is None, "refused as expected: " + line)
    # ---- marks
    for name, d in sorted(INDEX["names"].items()):
        v, body, line, _ = fetch("mark", [name])
        record("marks", "mark %s" % name, v is not None and str(v) == d["mark"], "expected %s, got %s" % (d["mark"], v))
    v, body, line, _ = fetch("mark", ["no_such_name"])
    record("marks", "mark of an unknown name", v is None, line)
    # ---- fail, unexported, slow
    v1, b1, l1, _ = fetch("fail", [])
    v2, b2, l2, _ = fetch("secret", [])
    record("fail", "fail: no reply, connection closes", v1 is None and l1.startswith("closed"), l1)
    record("fail", "an unexported name is refused", v2 is None and l2.startswith("closed"), l2)
    record("fail", "fail and a refusal look the same to the client", re.sub(r"peer=\S+", "", l1) == re.sub(r"peer=\S+", "", l2), "%r vs %r" % (l1, l2))
    v3, b3, l3, _ = fetch("events", [])
    record("fail", "a served name with the wrong number of arguments is refused (events/0)", v3 is None and l3.startswith("closed"), l3)
    v, body, line, dt = fetch("slow", [])
    r = ref("slow")
    record("slow", "slow answers after %.2f s (window %.1f to %.1f s)" % (dt, SLOW_MIN, SLOW_MAX),
           v is not None and v == etf.dec(r) and r[1:] in body and SLOW_MIN <= dt <= SLOW_MAX, line)


def report():
    width = max(len(r[1]) for r in rows)
    print()
    groups = []
    for g, label, ok, detail in rows:
        print("%-8s %-*s  %s  %s" % (g, width, label, "PASS" if ok else "FAIL", detail))
    total, bad = len(rows), [r for r in rows if not r[2]]
    print("\n%d checks, %d passed, %d failed" % (total, total - len(bad), len(bad)))
    for g, label, ok, detail in bad:
        print("  FAIL %s: %s" % (label, detail))
    open(os.path.join(RUN, "run_all.txt"), "w").write("\n".join("%s\t%s\t%s\t%s" % (g, l, "PASS" if o else "FAIL", d) for g, l, o, d in rows) + "\n")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
