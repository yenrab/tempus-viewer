#!/usr/bin/env python3
"""Checks that each TEMPUS node of the test network is up and doing its role. The network must be running (testnet/network.sh start).

    BEES_ROOT=... python3 run_tempus.py

Nodes: the sentinel (127.0.0.1:24430), edges 1 to 3 (24431 to 24433) and the bridge (24401). Everything is read the way a TEMPUS
client reads it, over TLS 1.3 with a token and proof of possession, with BEES's own Python example client (unchanged, from
BEES_ROOT): a `sample` request returns entries of one of the node's three stores (edge, bridge, sentinel), so what each node has
learned of the others can be seen from outside. The test unit that BEES's trials use (the nodes here are externally driven, as the
bridge is) accepts a `tick` frame, which makes the node run one step of a store: that is how the checks make an edge or the bridge
shuffle with a partner. A node's own log (testnet/run/NAME.log) is read for one thing only: whether a partner was admitted
(the line `admitted peer=...`), because no frame shows who dialed whom.
The checks:
  up         every node admits a client and answers with its own descriptor: its peer id and token type are the node's
  admission  a token that is expired, a token another producer signed, a bridge token on an edge's certificate and an edge
             token on a whitelisted certificate are each refused by every node that applies the rule (closed, no reply)
  join       after the start: the sentinel holds the three edges and the bridge; the bridge holds the three edges; every edge
             holds the sentinel, and every edge but the first holds the edge(s) that joined before it
  gossip     a tick of an edge's edge store has the edge learn the others (edge 1 learned nothing at its own join, it was
             first), a tick of its bridge store has it learn the bridge; a tick of edge 3 and of the bridge's edge store makes
             them shuffle with a partner, which is admitted there (log)
  groups     the three groups never mix: an edge's id is in no bridge or sentinel store, the bridge's in no edge or sentinel
             store, the sentinel's in no edge or bridge store
  roles      an edge and the sentinel do not serve calls (closed), as only a bridge does
Exit status 0 only when nothing failed. TEST data and TEST-ONLY keys of BEES; the clock is the nodes' fixed test clock 1500."""
import os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTNET = os.path.abspath(os.path.join(HERE, "..", ".."))
RUN = os.path.join(TESTNET, "run")
CERTS = None
sys.path.insert(0, HERE)
import call_home  # noqa: E402
sys.path.insert(0, os.path.join(TESTNET, "data"))
import etf  # noqa: E402

c = call_home.client_lib()
CERTS = os.path.join(os.environ["BEES_ROOT"], "trials", "t5_tempus_tls", "certs")
A = c.Atom
CLOCK, SKEW = 1500, 10
STORES = ("tempus_edge", "tempus_bridge", "tempus_sentinel")
SHUFFLE = {"tempus_edge": 3, "tempus_bridge": 2, "tempus_sentinel": 2}   # a sample asks for 1 to the store's shuffle length
# name -> (port, seed of its TEST-ONLY identity, type in its token)
NODES = {"sentinel": (24430, 128, "tempus_sentinel"), "edge1": (24431, 32, "tempus_edge"), "edge2": (24432, 192, "tempus_edge"),
         "edge3": (24433, 208, "tempus_edge"), "bridge": (24401, 160, "tempus_bridge")}
EDGES = ("edge1", "edge2", "edge3")
rows = []
FRESH = True
DONE = os.path.join(RUN, "tempus_checks.done")    # written when the checks have run; network.sh start removes it
VERIFIER = c.Verifier(c._raw_public(c.fixture_key(0)), "k1", lambda: CLOCK, SKEW)


def cert(name):
    return open(os.path.join(CERTS, name + ".pem"), "rb").read()


def token(seed, typ, exp=3000, signer=None):
    pub = c.fixture_identity(seed, typ, 1000, exp).pub
    return c.make_token(signer if signer is not None else c.fixture_key(0), "k1", pub, typ, 1000, exp)


# the client of the checks: an edge made from seed 112, no certificate of the whitelist; and the bridge-typed one (cert x4, seed 224)
ME = c.fixture_identity(112, "tempus_edge", 1000, 3000, addr="127.0.0.1:24439")
ME_BRIDGE = c.Identity(bytes(range(224, 256)), token(224, "tempus_bridge"), "127.0.0.1:24439", cert_pem=cert("x4"))
IDS = {n: c.fixture_identity(s, "tempus_edge", 1000, 3000).peer_id for n, (_p, s, _t) in NODES.items()}
SHORT = {n: i[:4].hex() for n, i in IDS.items()}
NAME_OF = {v: k for k, v in SHORT.items()}


def record(group, label, ok, detail=""):
    rows.append((group, label, bool(ok), detail))


def addr(n):
    return "127.0.0.1:%d" % NODES[n][0]


def ask(n, who, body, timeout=8.0):
    out = c.dial(addr(n), who, VERIFIER, body, timeout=timeout)
    time.sleep(0.15)
    return out


def client_for(n):
    """the sentinel puts every asker into its store of the asker's type: the checks ask it as a bridge, so its edge store keeps
    exactly the edges and a sample of it is complete"""
    return ME_BRIDGE if n == "sentinel" else ME


def sample(n, store, who=None):
    """-> the short ids (hex of the first 4 bytes) of the entries of the node's store, or None when no sample_reply came"""
    out = ask(n, who or client_for(n), c.sample(store, SHUFFLE[store]))
    if out.what != "reply" or out.kind != "sample_reply":
        return None
    return sorted(d[A("id")][:4].hex() for _age, d in out.fields["entries"])


def tick(n, store, who=ME):
    out = ask(n, who, c.tick(store))
    time.sleep(0.9)       # the shuffle the tick starts, and the connection actors' end
    return out.what == "reply" and out.kind == "done"


def names(shorts):
    return sorted(NAME_OF.get(s, s) for s in shorts) if shorts is not None else None


def log_count(node, short):
    try:
        text = open(os.path.join(RUN, node + ".log"), errors="replace").read()
    except OSError:
        return -1
    return len(re.findall(r"admitted peer=%s" % short, text))


def main():
    global FRESH
    FRESH = not os.path.exists(DONE)
    if not FRESH:
        print("note: these checks already ran against this network; the join checks that need a fresh start are weaker")
    # ---- up: every node admits a client and says who it is
    for n, (port, seed, typ) in NODES.items():
        out = ask(n, client_for(n), c.sample("tempus_sentinel", 1))
        peer = out.advert[A("id")][:4].hex() if out.advert else None
        record("up", "%s (port %d) answers a sample request" % (n, port), out.what == "reply" and out.kind == "sample_reply", out.line()[:100])
        record("up", "%s says who it is: peer %s, token type %s" % (n, SHORT[n], typ), peer == SHORT[n] and out.typ == typ,
               "peer %s typ %s" % (peer, out.typ))
    # ---- admission
    bad = {"an expired token": ME.with_token(token(112, "tempus_edge", exp=1400)),
           "a token another producer signed": ME.with_token(token(112, "tempus_edge", signer=c.fixture_key(96)))}
    for n in NODES:
        for what, who in bad.items():
            out = ask(n, who, c.sample("tempus_sentinel", 1))
            record("admission", "%s refuses %s" % (n, what), out.what == "closed", out.line()[:100])
    # a certificate on the whitelist (x4) with an edge token, and a bridge token on a certificate that is not listed
    wl_edge = c.Identity(bytes(range(224, 256)), token(224, "tempus_edge"), "127.0.0.1:24439", cert_pem=cert("x4"))
    not_wl_bridge = c.fixture_identity(112, "tempus_bridge", 1000, 3000, addr="127.0.0.1:24439")
    for n in ("sentinel", "edge1", "bridge"):
        out = ask(n, wl_edge, c.sample("tempus_sentinel", 1))
        record("admission", "%s refuses an edge token on a whitelisted certificate" % n, out.what == "closed", out.line()[:100])
        out = ask(n, not_wl_bridge, c.sample("tempus_sentinel", 1))
        record("admission", "%s refuses a bridge token on a certificate that is not listed" % n, out.what == "closed", out.line()[:100])
    out = ask("sentinel", ME_BRIDGE, c.sample("tempus_sentinel", 1))
    record("admission", "sentinel admits a bridge-typed client with a whitelisted certificate", out.what == "reply" and out.kind == "sample_reply", out.line()[:100])

    # ---- join: what each node learned at the start (the sentinel is asked as a bridge, see client_for)
    s_edges = sample("sentinel", "tempus_edge")
    record("join", "sentinel holds the three edges", names(s_edges) == sorted(EDGES), "got %s" % names(s_edges))
    s_br = sample("sentinel", "tempus_bridge")
    record("join", "sentinel holds the bridge", s_br is not None and SHORT["bridge"] in s_br, "got %s" % names(s_br))
    b_edges = sample("bridge", "tempus_edge")
    record("join", "bridge learned the three edges", names(b_edges) == sorted(EDGES), "got %s" % names(b_edges))
    for n in EDGES + ("bridge",):
        s = sample(n, "tempus_sentinel")
        record("join", "%s holds the sentinel" % n, s == [SHORT["sentinel"]], "got %s" % names(s))
    e2, e3 = sample("edge2", "tempus_edge"), sample("edge3", "tempus_edge")
    if FRESH:
        record("join", "edge2 holds edge1 (it joined before)", e2 is not None and SHORT["edge1"] in e2, "got %s" % names(e2))
        record("join", "edge3 holds edge1 and edge2", e3 is not None and {SHORT["edge1"], SHORT["edge2"]} <= set(e3), "got %s" % names(e3))
        e1 = sample("edge1", "tempus_edge")
        record("join", "edge1 held no edge at its own join (it was the first)", e1 == [], "got %s" % names(e1))
    else:
        # an earlier run of these checks ticked the stores: the views have been shuffled since the start (restart the network for the strict form)
        record("join", "edge2 and edge3 each hold another edge, and neither holds itself (not a fresh start)",
               all(s and SHORT[n] not in s for n, s in (("edge2", e2), ("edge3", e3))), "edge2 %s, edge3 %s" % (names(e2), names(e3)))

    # ---- gossip
    ok = tick("edge1", "tempus_edge")
    e1 = sample("edge1", "tempus_edge")
    record("gossip", "after a tick of its edge store edge1 has learned other edges (from the sentinel)",
           ok and e1 is not None and len(e1) >= 1 and SHORT["edge1"] not in e1, "tick %s, got %s" % (ok, names(e1)))
    for n in EDGES:
        ok = tick(n, "tempus_bridge")
        s = sample(n, "tempus_bridge")
        record("gossip", "after a tick of its bridge store %s holds the bridge" % n, ok and s is not None and SHORT["bridge"] in s,
               "tick %s, got %s" % (ok, names(s)))
    before = {n: log_count(n, SHORT["edge3"]) for n in ("edge1", "edge2")}
    ok = tick("edge3", "tempus_edge")
    after = {n: log_count(n, SHORT["edge3"]) for n in ("edge1", "edge2")}
    record("gossip", "a tick of edge3's edge store makes it shuffle with an edge, which admits edge3",
           ok and any(after[n] > before[n] for n in before), "tick %s, admitted lines before %s after %s" % (ok, before, after))
    before = {n: log_count(n, SHORT["bridge"]) for n in EDGES}
    ok = tick("bridge", "tempus_edge")
    after = {n: log_count(n, SHORT["bridge"]) for n in EDGES}
    record("gossip", "a tick of the bridge's edge store makes it shuffle with an edge, which admits the bridge",
           ok and any(after[n] > before[n] for n in EDGES), "tick %s, admitted lines before %s after %s" % (ok, before, after))
    b_edges = sample("bridge", "tempus_edge")
    record("gossip", "the bridge still holds the three edges after its shuffle", names(b_edges) == sorted(EDGES), "got %s" % names(b_edges))

    # ---- groups never mix: every store of every node
    mix = []
    allowed = {"tempus_edge": set(EDGES), "tempus_bridge": {"bridge"}, "tempus_sentinel": {"sentinel"}}
    for n in NODES:
        for st in STORES:
            s = sample(n, st)
            if s is None:
                mix.append("%s/%s: no sample" % (n, st))
                continue
            for short in s:
                who_is = NAME_OF.get(short)
                # the clients of these checks (x4, seed 112) may sit in a sentinel's stores; every other id must be of the store's type
                if who_is is not None and who_is not in allowed[st]:
                    mix.append("%s/%s holds %s" % (n, st, who_is))
    record("groups", "no store of any node holds a peer of another type (%d stores)" % (len(NODES) * len(STORES)), not mix, "; ".join(mix) or "all clean")

    # ---- roles: only a bridge serves calls
    for n in ("sentinel", "edge1", "edge2", "edge3"):
        out = ask(n, ME, c.call_frame("t1", "viewer", "home", []))
        record("roles", "%s does not serve a call (closed, no reply)" % n, out.what == "closed", out.line()[:100])
    # the BEES client reads no tuples, so a result that carries commands arrives as "refused ... bad_tag" with the frame in out.body
    # (as in run_all.py): the frame is read with the testnet's own reader
    out = call_home.call(addr("bridge"), "empty", [], req_id="t2")
    frame = None
    try:
        frame = etf.dec(out.body) if out.body else None
    except Exception:
        pass
    record("roles", "the bridge answers a call (viewer:empty/0 gives a result frame)",
           isinstance(frame, dict) and str(frame.get("t")) == "result", out.line()[:100])
    with open(DONE, "w") as f:
        f.write("the TEMPUS checks ran against this network\n")
    return report()


def report():
    width = max(len(r[1]) for r in rows)
    group = None
    for g, label, ok, detail in rows:
        if g != group:
            print("\n[%s]" % g)
            group = g
        print("  %s  %s  %s" % ("PASS" if ok else "FAIL", label.ljust(width), "" if ok else detail))
    bad = [r for r in rows if not r[2]]
    print("\nTEMPUS nodes: %d checks, %d passed, %d failed" % (len(rows), len(rows) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
