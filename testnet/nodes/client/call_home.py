#!/usr/bin/env python3
"""The slice's client: dials the bridge over TEMPUS (TLS 1.3, mutual, tempus/1), sends a TRUST call (module viewer,
function NAME, 0 arguments) and compares the value of the `result` frame with testnet/data/out/replies/NAME.etf.

    BEES_ROOT=... python3 call_home.py [--addr 127.0.0.1:24401] [--name home]

BEES's Python example client (example_tempus_clients/python) is imported from BEES_ROOT, unchanged. Its test-only identity and
token (an edge, made from a fixed seed and signed by the test producer) and its verifier are BEES's own fixtures, as in the
c3 trial. Exit status 0 when the decoded values are equal. TEST network only."""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTNET = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(TESTNET, "data"))
import etf  # noqa: E402  the testnet's own reader, independent of BEES and Silica


def client_lib():
    root = os.environ.get("BEES_ROOT") or sys.exit("set BEES_ROOT to the project-bees clone")
    sys.path.insert(0, os.path.join(root, "example_tempus_clients", "python"))
    import bees_tempus_client as c
    return c


def call(addr, name="home", args=(), req_id="home1", clock=1500, skew=10):
    """one TRUST call through the bridge; returns BEES's Outcome"""
    c = client_lib()
    # the c3 trial's Python client: identity "other" (seed 64..95), an edge token valid 1000..3000, the verifier with the
    # test producer's key and the trial's clock 1500 (the bridge's own test clock is the same)
    me = c.fixture_identity(64, "tempus_edge", 1000, 3000, addr="127.0.0.1:24402")
    verifier = c.Verifier(c._raw_public(c.fixture_key(0)), "k1", lambda: clock, skew)
    return c.dial(addr, me, verifier, c.call_frame(req_id, "viewer", name, list(args)), timeout=10.0)


def find_value_bytes(body, ref):
    """whether the reference's bytes (without the version byte) appear verbatim in the result frame's body"""
    return ref[1:] in body


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default="127.0.0.1:24401")
    ap.add_argument("--name", default="home")
    a = ap.parse_args(argv)
    out = call(a.addr, a.name)
    print("outcome:", out.line()[:300])
    # BEES's Python reader has no tuples (its docstring: a TRUST frame carrying them is "undecoded", the bytes stay in out.body), and
    # every command is a tuple, so a good result frame arrives as refused/reply/bad_tag with the whole frame in out.body. We
    # take the frame from out.body and read it with the testnet's own reader; a result frame it can read is what we want.
    try:
        frame = etf.dec(out.body)
    except Exception as e:
        frame = None
    if not isinstance(frame, dict) or str(frame.get("t")) != "result" or "value" not in frame:
        print("FAIL: no result frame")
        return 1
    ref = open(os.path.join(TESTNET, "data", "out", "replies", a.name + ".etf"), "rb").read()
    got, want = frame["value"], etf.dec(ref)
    print("result frame: %d bytes; keys: %s" % (len(out.body), ", ".join(sorted(frame))))
    equal = got == want
    print("decoded value equals the term of %s.etf: %s" % (a.name, "YES" if equal else "NO"))
    print("the reference's bytes appear verbatim inside the result frame (byte-identical value): %s" % ("YES" if find_value_bytes(out.body, ref) else "NO"))
    print("re-encoded value equals the reference bytes (etf.py's canonical writer): %s" % ("YES" if etf.enc(got) == ref else "NO"))
    if not equal:
        print("got :", etf.show(got)[:600]); print("want:", etf.show(want)[:600])
    print("SUCCESS" if equal else "FAIL")
    return 0 if equal else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
