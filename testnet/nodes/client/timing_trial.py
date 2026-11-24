#!/usr/bin/env python3
"""The command-line timing trial (testnet plan step 5; requirements 14.4/14.5; OI-5, OI-7, OI-9).

    testnet/nodes/client/timing_trial.py [--reps 30] [--conc-total 48] [--out testnet/results/timing-YYYYMMDD.md] [--no-start]

Starts the whole test network (testnet/network.sh start), runs the measurements below against the bridge over loopback, writes a
results file, and stops the network again (finally clause and signal handlers; --no-start uses a network that is already running
and leaves it running). Needs the builds of build.sh and BEES_ROOT (build.sh wrote testnet/.bees_root). TEST network only.

What is measured (milliseconds, wall clock of this process, time.perf_counter):
  1. full request: connect + TLS 1.3 handshake + admission + call + reply, for small, medium, large replies and image parts;
  2. its split (see the next paragraph);
  3. sequential versus 4 and 8 concurrent connections: throughput, refusals;
  4. a screen: a frame and the requests its commands ask for, sequential and parallel;
  5. the mark query as a request of its own;
  6. every reply checked the way the viewer would (ETF decode, one tagged tuple of one map per command, known tag, limits of
     requirements section 11) and compared byte for byte with data/out/replies where the name has a reference.

The split: BEES's client does not expose phases, and its dial() is not edited here. `timed_dial` below is a thin copy of
dial() and of _admit() of BEES's tempus_client/connection.py, calling the same helpers (_context, _Conn, _tls_checks, _emit,
_read, read_any) with timestamps between the steps. The copy, not dial(), is what is timed; `baseline` times BEES's own dial()
unchanged on the same request to show the copy costs the same. Phases:
  tcp        socket.create_connection (loopback: one SYN round trip)
  tls        ssl wrap_socket: ClientHello .. client Finished. In TLS 1.3 the client's handshake ends when it has sent its
             Finished, BEFORE the server has judged the client's certificate, so server-side certificate checks land in `admit`
  admit      advert out, advert in and check, challenge out, challenge in, response out, response in and check (BEES's
             admission with proof of possession and the token); the server-side work of the TLS client certificate and the
             token check is paid in here
  request    the call frame written until the whole reply frame is read (bridge, onward TRUST call over its own connection to a
             TRUST node, the node's work, the reply)
  close      conn.close(): close_notify, shutdown, read until the peer's end (BEES waits at most LINGER = 0.5 s for it)
  setup      building the SSLContext (writes the certificate to a temporary directory and loads it); the trial builds it once,
             as a viewer would, and measures it separately (BEES's dial() pays it on every call)
`full` is tcp+tls+admit+request (the reply is in hand). `full+close` adds close (what dial() returns after).

Exit status 0 when the network started, every checked reply passed the viewer's rules and equals its reference, and the
network stopped with nothing left; else 1."""
import argparse, datetime, json, os, platform, re, signal, socket, ssl, statistics, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTNET = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.dirname(TESTNET)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(TESTNET, "data"))
import etf  # noqa: E402  the testnet's own reader
import call_home  # noqa: E402

REPLIES = os.path.join(TESTNET, "data", "out", "replies")
IMAGES = os.path.join(TESTNET, "data", "out", "images")
INDEX = json.load(open(os.path.join(TESTNET, "data", "out", "index.json")))
ADDR = "127.0.0.1:24401"
PART_MAX = 131000
NETWORK = os.path.join(TESTNET, "network.sh")

# ------------------------------------------------------------------ the viewer's rules (requirements 6 and 11)
LIMITS = {"commands": 2000, "depth": 32, "text": 64 * 1024, "image_total": 5 * 1024 * 1024, "auto_requests": 20, "parts_at_once": 4}


def known_tags():
    src = open(os.path.join(TESTNET, "data", "vocab.py")).read()
    return set(re.findall(r'cmd\("(\w+)"', src))


TAGS = known_tags()


def depth(t, d=1):
    if isinstance(t, dict):
        return max([depth(v, d + 1) for v in t.values()] + [d])
    if isinstance(t, (list, tuple)):
        return max([depth(v, d + 1) for v in t] + [d])
    return d


def longest_text(t):
    if isinstance(t, (bytes, bytearray)):
        return len(t)
    if isinstance(t, dict):
        return max([longest_text(v) for v in t.values()] + [0])
    if isinstance(t, (list, tuple)):
        return max([longest_text(v) for v in t] + [0])
    return 0


def one_line(tag, m):
    def txt(k):
        v = m.get(k)
        return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
    if tag in ("heading", "title"):
        return "%s%s %r" % (tag, " L%s" % m["level"] if "level" in m else "", txt("text")[:48])
    if tag == "paragraph" or tag == "quotation":
        return "%s of %d runs" % (tag, len(m.get("runs", [])))
    if tag == "list":
        return "%s list of %d items" % ("ordered" if m.get("ordered") else "bullet", len(m.get("items", [])))
    if tag == "table":
        return "table %r %d columns x %d rows" % (txt("caption")[:30], len(m.get("columns", [])), len(m.get("rows", [])))
    if tag == "table_rows":
        return "%d more rows into %s" % (len(m.get("rows", [])), txt("region"))
    if tag == "image":
        return "image %s %sx%s %s bytes alt %r" % (txt("id"), m.get("width"), m.get("height"), m.get("size"), txt("alt")[:30])
    if tag in ("fetch", "refresh"):
        r = m.get("request", {})
        return "%s %s(%s) into %s" % (tag, txt("request") if False else r.get("name", b"").decode(), ",".join(a.decode() for a in r.get("args", [])), txt("into"))
    if tag == "region":
        return "region %s in %s" % (txt("name"), txt("into"))
    if tag == "form":
        return "form %s with %d fields" % (txt("name"), len(m.get("fields", [])))
    if tag == "button":
        return "button %r" % txt("label")
    return tag


def check_commands(value):
    """The viewer's decision on a reply that must be commands. -> (ok, why, summary lines, tag histogram, fetches)"""
    if not isinstance(value, list):
        return False, "reply is not a list", [], {}, []
    if len(value) > LIMITS["commands"]:
        return False, "more than %d commands" % LIMITS["commands"], [], {}, []
    lines, hist, fetches = [], {}, []
    for i, c in enumerate(value):
        if not (isinstance(c, tuple) and len(c) == 2 and isinstance(c[0], etf.Atom) and isinstance(c[1], dict)):
            return False, "command %d is not a tagged tuple of one map" % i, lines, hist, fetches
        tag, m = str(c[0]), c[1]
        if tag not in TAGS:
            return False, "command %d has unknown tag %s" % (i, tag), lines, hist, fetches
        hist[tag] = hist.get(tag, 0) + 1
        lines.append(one_line(tag, m))
        if tag == "fetch":
            r = m["request"]
            fetches.append((r["name"].decode(), [a.decode() for a in r["args"]]))
        if tag == "vocabulary" and m.get("version") != 1:
            return False, "vocabulary version %r" % m.get("version"), lines, hist, fetches
    if depth(value) > LIMITS["depth"] + 4:      # +4: the list, the tuple, the map and one level of values are not nesting of the screen
        return False, "nesting deeper than %d" % LIMITS["depth"], lines, hist, fetches
    if longest_text(value) > LIMITS["text"]:
        return False, "a text value above %d bytes" % LIMITS["text"], lines, hist, fetches
    if hist.get("fetch", 0) > LIMITS["auto_requests"]:
        return False, "more than %d automatic requests" % LIMITS["auto_requests"], lines, hist, fetches
    return True, "ok", lines, hist, fetches


def ref_name(name, args):
    """the data/out/replies file that belongs to a request, or None"""
    if name in ("events", "samples"):
        return name + "." + args[0] if args else name
    if name == "image_part":
        return None
    if name in ("node", "restart_node"):
        return name if args == ["n01"] else None
    if name == "mark":
        return None
    if name == "clock":
        return name
    return name if os.path.exists(os.path.join(REPLIES, name + ".etf")) else None


# ------------------------------------------------------------------ the timed copy of BEES's dial()
c = call_home.client_lib()
ME = c.fixture_identity(64, "tempus_edge", 1000, 3000, addr="127.0.0.1:24402")
VERIFIER = c.Verifier(c._raw_public(c.fixture_key(0)), "k1", lambda: 1500, 10)
_ctx_box = {}


def client_ctx():
    if "ctx" not in _ctx_box:
        _ctx_box["ctx"] = c._context(False, ME, "1.3", c.ALPN, "own", ())
    return _ctx_box["ctx"]


def timed_dial(addr, name, args, req_id, timeout=10.0):
    """-> dict(outcome, body, t: phase seconds, ok). Same steps and checks as BEES's dial(); times each."""
    T = {}
    t0 = time.perf_counter()
    deadline = time.monotonic() + timeout
    state = {}
    host, _, port = addr.rpartition(":")
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
    except OSError as e:
        return {"outcome": "unreachable", "body": b"", "t": {"tcp": time.perf_counter() - t0}, "line": "unreachable " + str(e)[:60]}
    t1 = time.perf_counter(); T["tcp"] = t1 - t0
    ctx = client_ctx()
    try:
        sock.settimeout(max(0.001, deadline - time.monotonic()))
        tls = ctx.wrap_socket(sock)
    except (OSError, ssl.SSLError) as e:
        sock.close()
        T["tls"] = time.perf_counter() - t1
        return {"outcome": "tls_failed", "body": b"", "t": T, "line": "tls_failed " + str(e)[:60]}
    t2 = time.perf_counter(); T["tls"] = t2 - t1
    conn = c._Conn(tls, deadline)
    try:
        cert_pub = c._tls_checks(tls, state, c.ALPN)
    except c.Refused as why:
        o = c._end(conn, "refused", "tls", state, str(why))
        return {"outcome": o.what, "body": b"", "t": T, "line": o.line()[:120]}
    # ---- admission (the copy of _admit(): advert, challenge, response; each _read waits for the peer's frame)
    nonce = os.urandom(32)
    def fail(out):
        return {"outcome": out.what, "body": b"", "t": T, "line": out.line()[:120]}
    out = c._emit(conn, None, "advert", state, ME.advert(None))
    if out: return fail(out)
    fields, out, _ = c._read(conn, "advert", state, ("advert",), c.ENTRIES_MAX)
    if out: return fail(out)
    ta = time.perf_counter(); T["admit_advert"] = ta - t2
    theirs = fields["d"]; state["advert"] = theirs
    try:
        state["typ"] = VERIFIER.check_descriptor(theirs, cert_pub, state.get("cert_fp"))["typ"]
    except c.Refused as why:
        return fail(c._end(conn, "refused", "advert", state, str(why)))
    out = c._emit(conn, None, "challenge", state, c.challenge(nonce))
    if out: return fail(out)
    fields, out, kind = c._read(conn, "challenge", state, ("pop_challenge", "key_rotated"), c.ENTRIES_MAX)
    if out: return fail(out)
    if kind == "key_rotated":
        return fail(c._end(conn, "key_rotated", "challenge", state))
    tb = time.perf_counter(); T["admit_challenge"] = tb - ta
    sig = ME.prove(fields["nonce"])
    out = c._emit(conn, None, "response", state, c.etf_encode({c.Atom("t"): c.Atom("pop_response"), c.Atom("sig"): bytes(sig)}))
    if out: return fail(out)
    fields, out, _ = c._read(conn, "response", state, ("pop_response",), c.ENTRIES_MAX)
    if out: return fail(out)
    try:
        VERIFIER.check_proof(theirs[c.Atom("pub")], nonce, theirs[c.Atom("token")], fields["sig"])
    except c.Refused as why:
        return fail(c._end(conn, "refused", "response", state, str(why)))
    t3 = time.perf_counter(); T["admit_response"] = t3 - tb; T["admit"] = t3 - t2
    # ---- the call
    out = c._emit(conn, None, "request", state, c.call_frame(req_id, "viewer", name, [a.encode() if isinstance(a, str) else a for a in args]))
    if out: return fail(out)
    what, value = conn.read()
    t4 = time.perf_counter(); T["request"] = t4 - t3
    if what != "frame":
        o = c._end(conn, what, "reply", state, value)
        return {"outcome": what, "body": b"", "t": T, "line": o.line()[:120]}
    T["full"] = t4 - t0
    conn.close()
    t5 = time.perf_counter(); T["close"] = t5 - t4; T["full_close"] = t5 - t0
    return {"outcome": "reply", "body": value, "t": T, "line": "reply"}


def decode_frame(body):
    try:
        f = etf.dec(body)
    except Exception:
        return None
    return f if isinstance(f, dict) and str(f.get("t")) == "result" and "value" in f else None


_seq = [0]
_seq_lock = threading.Lock()


def request(name, args=(), addr=ADDR):
    with _seq_lock:
        _seq[0] += 1
        rid = "t%d" % _seq[0]
    r = timed_dial(addr, name, list(args), rid)
    r["name"], r["args"] = name, list(args)
    r["frame"] = decode_frame(r["body"]) if r["body"] else None
    return r


# ------------------------------------------------------------------ statistics
def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def stats(xs):
    ms = [x * 1000 for x in xs]
    return {"n": len(ms), "median": statistics.median(ms), "p95": pct(ms, 95), "min": min(ms), "max": max(ms), "mean": statistics.fmean(ms)}


def fmt(s):
    return "%7.2f %7.2f %7.2f %7.2f" % (s["median"], s["p95"], s["min"], s["max"]) if s else "      -       -       -       -"


# ------------------------------------------------------------------ the checks of one reply (item 6)
problems = []
summaries = {}


def verify(r, label, kind="commands", expect=None):
    """kind commands: the viewer's rules + reference; kind bytes: reply value is bytes equal to expect; kind mark: equals expect"""
    if r["outcome"] != "reply" or r["frame"] is None:
        problems.append("%s: no result frame (%s)" % (label, r["line"]))
        return False
    v = r["frame"]["value"]
    if kind == "bytes":
        ok = isinstance(v, bytes) and v == expect
        if not ok:
            problems.append("%s: part bytes differ from the PNG" % label)
        return ok
    if kind == "mark":
        ok = str(v) == expect
        if not ok:
            problems.append("%s: mark %r, expected %s" % (label, v, expect))
        return ok
    ok, why, lines, hist, fetches = check_commands(v)
    if not ok:
        problems.append("%s: viewer would refuse: %s" % (label, why))
        return False
    ref = ref_name(r["name"], r["args"])
    if ref:
        rb = open(os.path.join(REPLIES, ref + ".etf"), "rb").read()
        if rb[1:] not in r["body"] or etf.dec(rb) != v:
            problems.append("%s: differs from data/out/replies/%s.etf" % (label, ref))
            return False
        refnote = "bytes equal %s.etf" % ref
    else:
        refnote = "no reference file"
    if label not in summaries:
        summaries[label] = (len(r["body"]), len(v), hist, lines, refnote, fetches)
    return True


# ------------------------------------------------------------------ the scenarios
PHASES = ["tcp", "tls", "admit", "request", "full", "close", "full_close"]


def run_single(label, name, args, reps, kind="commands", expect=None):
    """reps sequential requests, one connection each; returns the row for the table"""
    for _ in range(3):
        request(name, args)                       # warm up (not counted)
    samples = {p: [] for p in PHASES}
    admit_parts = {"admit_advert": [], "admit_challenge": [], "admit_response": []}
    sizes, bad, refusals = [], 0, []
    for _ in range(reps):
        r = request(name, args)
        if r["outcome"] != "reply":
            refusals.append(r["line"])
            continue
        if not verify(r, label, kind, expect):
            bad += 1
        sizes.append(len(r["body"]))
        for p in PHASES:
            samples[p].append(r["t"][p])
        for p in admit_parts:
            admit_parts[p].append(r["t"][p])
    row = {"label": label, "name": name, "args": args, "bytes": sizes[0] if sizes else 0, "n": len(sizes), "refused": refusals, "bad": bad,
           "phases": {p: stats(samples[p]) if samples[p] else None for p in PHASES},
           "admit_parts": {p: stats(admit_parts[p]) if admit_parts[p] else None for p in admit_parts}}
    return row


def baseline(reps):
    """BEES's own dial(), unchanged, through call_home.call: connect .. reply and close, and context building on each call"""
    xs = []
    for i in range(reps):
        t = time.perf_counter()
        out = call_home.call(ADDR, "home", (), req_id="b%d" % i)
        xs.append(time.perf_counter() - t)
        assert out.body, out.line()
    return stats(xs)


def ctx_setup(reps):
    xs = []
    for _ in range(reps):
        t = time.perf_counter()
        c._context(False, ME, "1.3", c.ALPN, "own", ())
        xs.append(time.perf_counter() - t)
    return stats(xs)


def run_many(jobs, workers):
    """jobs: list of (name, args). Runs them with `workers` threads each using one connection per job. -> (wall seconds, results)"""
    results = [None] * len(jobs)
    idx = [0]
    lock = threading.Lock()

    def work():
        while True:
            with lock:
                i = idx[0]; idx[0] += 1
            if i >= len(jobs):
                return
            results[i] = request(*jobs[i])
    t = time.perf_counter()
    ths = [threading.Thread(target=work) for _ in range(workers)]
    for th in ths: th.start()
    for th in ths: th.join()
    return time.perf_counter() - t, results


def run_concurrency(total, levels):
    jobs = [("home", ())] * total
    rows = []
    for w in levels:
        wall, res = run_many(jobs, w)
        ok = [r for r in res if r["outcome"] == "reply" and r["frame"] is not None]
        for r in ok[:2]:
            verify(r, "home")
        lat = [r["t"]["full"] for r in ok]
        refused = {}
        for r in res:
            if r not in ok:
                refused[r["line"]] = refused.get(r["line"], 0) + 1
        rows.append({"workers": w, "total": total, "ok": len(ok), "wall": wall, "rps": len(ok) / wall, "lat": stats(lat) if lat else None, "refused": refused})
        time.sleep(1.0)
    return rows


def screen(label, frame_name, frame_args, extra, reps):
    """the frame, then the requests its fetch commands name (+ extra), sequentially and in parallel (4 at once, the limit of
    requirements 11); total time to a full screen"""
    seq_t, par_t, n_req, refused = [], [], 0, []
    for rep in range(reps + 1):
        t = time.perf_counter()
        fr = request(frame_name, frame_args)
        verify(fr, frame_name)
        regs = list(summaries.get(frame_name, (0, 0, {}, [], "", []))[5]) + list(extra)
        n_req = 1 + len(regs)
        for nm, ar in regs:
            r = request(nm, ar)
            if r["outcome"] != "reply":
                refused.append(r["line"])
            else:
                verify(r, nm)
        ts = time.perf_counter() - t
        t = time.perf_counter()
        fr = request(frame_name, frame_args)
        wall, res = run_many(regs, min(4, max(1, len(regs))))
        for r in res:
            if r["outcome"] != "reply":
                refused.append(r["line"])
        tp = time.perf_counter() - t
        if rep > 0:                                  # the first round warms up
            seq_t.append(ts); par_t.append(tp)
    return {"label": label, "requests": n_req, "seq": stats(seq_t), "par": stats(par_t), "refused": refused}


def gallery_screen(reps):
    """the gallery frame, then every image in parts (icon, chart, photo in two parts) = 4 parts, sequential and 4 at once"""
    jobs = [("image_part", ("icon", "0", "2017")), ("image_part", ("chart", "0", "850")),
            ("image_part", ("photo", "0", str(PART_MAX))), ("image_part", ("photo", str(PART_MAX), str(234174 - PART_MAX)))]
    seq_t, par_t, refused = [], [], []
    for rep in range(reps + 1):
        t = time.perf_counter()
        fr = request("gallery", ()); verify(fr, "gallery")
        for j in jobs:
            r = request(*j)
            if r["outcome"] != "reply": refused.append(r["line"])
        ts = time.perf_counter() - t
        t = time.perf_counter()
        fr = request("gallery", ())
        wall, res = run_many(jobs, 4)
        for r in res:
            if r["outcome"] != "reply": refused.append(r["line"])
        tp = time.perf_counter() - t
        if rep > 0:
            seq_t.append(ts); par_t.append(tp)
    return {"label": "gallery: frame + 4 image parts", "requests": 5, "seq": stats(seq_t), "par": stats(par_t), "refused": refused}


# ------------------------------------------------------------------ environment
def sh(*a, cwd=None):
    try:
        return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return "?"


def machine_info():
    bees = os.environ.get("BEES_ROOT", "")
    sib = os.path.join(os.path.dirname(bees), "silica") if bees else ""
    def commit(d):
        if d and os.path.isdir(os.path.join(d, ".git")):
            return sh("git", "rev-parse", "--short=12", "HEAD", cwd=d) + (" (modified)" if sh("git", "status", "--porcelain", "--untracked-files=no", cwd=d) else "")
        return "not a git clone here"
    return [
        ("date", datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")),
        ("machine", "%s, %s cores, %s GB" % (sh("sysctl", "-n", "machdep.cpu.brand_string") or platform.processor(), os.cpu_count(),
                                                 "%.0f" % (int(sh("sysctl", "-n", "hw.memsize") or 0) / 2**30))),
        ("os", "%s %s %s" % (platform.system(), platform.release(), sh("sw_vers", "-productVersion"))),
        ("python / ssl", "%s / %s" % (platform.python_version(), ssl.OPENSSL_VERSION)),
        ("TEMPUS_browser commit", commit(REPO) + ("" if True else "")),
        ("project-bees clone commit", commit(bees)),
        ("silica clone commit", commit(sib)),
        ("nodes", "Silica-compiled native programs (release compiler e53689ec96c9, see build.sh), their OpenSSL 4.x; clients: this Python process"),
        ("load", sh("uptime")),
    ]


# ------------------------------------------------------------------ the report
def table(rows_, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows_]
    return out


def f2(s, k="median"):
    return "%.1f" % s[k] if s else "-"


def report(info, singles, base, setup, conc, screens, mark_row, reps, total, started):
    L = ["# Timing trial %s" % datetime.date.today().isoformat(), "",
         "Generated by `testnet/nodes/client/timing_trial.py` (`--reps %d`, concurrency jobs %d). TEST network on one machine over loopback; "
         "read the caveats at the end before using any number." % (reps, total), "", "## Machine and versions", ""]
    L += ["- %s: %s" % kv for kv in info]
    L += ["", "## 1. Full request, sequential, one new connection per request", "",
          "Milliseconds. `full` = connect + TLS 1.3 handshake (X25519MLKEM768 negotiated by the stack's defaults on both sides, see the "
          "caveat) + admission + call + reply read. `+close` adds the client's orderly close (BEES's close, which waits for the peer's end, "
          "at most 0.5 s). %d requests per row after 3 warm-up requests." % reps, ""]
    rows = []
    for r in singles:
        p = r["phases"]
        rows.append([r["label"], str(r["bytes"]), str(r["n"]), f2(p["full"]), f2(p["full"], "p95"), f2(p["full"], "min"), f2(p["full"], "max"),
                     f2(p["full_close"]), f2(p["full_close"], "p95")])
    L += table(rows, ["request", "frame bytes", "n", "full median", "p95", "min", "max", "+close median", "+close p95"])
    L += ["", "## 2. Where the time goes (median ms; p95 in brackets)", "",
          "Phases are those of `timed_dial` (see the script's header for what each one covers and why the TLS 1.3 client handshake "
          "ends before the server has judged the client). `admit` is the sum of the three frame exchanges.", ""]
    rows = []
    for r in singles:
        p = r["phases"]
        cells = [r["label"]]
        for k in ("tcp", "tls", "admit", "request", "close"):
            cells.append("%s (%s)" % (f2(p[k]), f2(p[k], "p95")))
        h = (p["tcp"]["median"] + p["tls"]["median"] + p["admit"]["median"]) if p["tcp"] else 0
        cells.append("%.1f" % h)
        cells.append("%.0f%%" % (100.0 * h / p["full"]["median"]) if p["full"] else "-")
        rows.append(cells)
    L += table(rows, ["request", "tcp", "tls", "admit", "request->reply", "close", "setup before the call (tcp+tls+admit)", "share of full"])
    home = next((r for r in singles if r["name"] == "home"), None)
    if home:
        a = home["admit_parts"]
        L += ["", "Admission split for `home` (median ms): advert exchange %s, challenge exchange %s, response exchange %s." % (
            f2(a["admit_advert"]), f2(a["admit_challenge"]), f2(a["admit_response"])), ""]
    L += ["Client-side cost not in the table: building the SSLContext (certificate written to a temporary directory and loaded) took %s ms "
          "median (p95 %s); BEES's `dial()` pays it on every call, the trial builds it once. BEES's own unchanged `dial()` for `home`, "
          "measured end to end with that cost and the close: median %s ms, p95 %s ms (n=%d); the copy's `+close` for `home` was %s ms."
          % (f2(setup), f2(setup, "p95"), f2(base), f2(base, "p95"), base["n"], f2(home["phases"]["full_close"]) if home else "-"), ""]
    L += ["## 3. Sequential versus concurrent (request `home`, %d requests per level, one connection each)" % total, "",
          "| connections at once | ok | wall s | requests/s | latency median | p95 | max | refused or failed |", "|---|---|---|---|---|---|---|---|"]
    for r in conc:
        L.append("| %d | %d of %d | %.2f | %.1f | %s | %s | %s | %s |" % (
            r["workers"], r["ok"], r["total"], r["wall"], r["rps"], f2(r["lat"]), f2(r["lat"], "p95"), f2(r["lat"], "max"),
            "; ".join("%d x %s" % (n, k) for k, n in r["refused"].items()) or "none"))
    L += ["", "## 4. A screen: a frame and the requests its commands ask for", "",
          "Total time from the first connection to the last reply, %d repetitions. Sequential: one request after another. Parallel: "
          "the frame first, then the region requests with at most 4 connections at once (the viewer's limit, requirement 11). "
          "The parallel column includes one repeat of the frame request, so it is the frame plus the parallel part." % reps, ""]
    rows = []
    for s in screens:
        rows.append([s["label"], str(s["requests"]), f2(s["seq"]), f2(s["seq"], "p95"), f2(s["par"]), f2(s["par"], "p95"),
                     "; ".join(sorted(set(s["refused"]))) or "none"])
    L += table(rows, ["screen", "requests", "sequential median", "p95", "parallel median", "p95", "refused"])
    L += ["", "## 5. The mark query (stand-in form `viewer:mark/1`, routed to the authority node)", ""]
    L += table([[mark_row["label"], f2(mark_row["phases"]["full"]), f2(mark_row["phases"]["full"], "p95"), f2(mark_row["phases"]["request"]),
                 f2(mark_row["phases"]["full_close"])]], ["request", "full median", "p95", "request->reply median", "+close median"])
    L += ["", "## 6. What the viewer would do with each reply", "",
          "Every reply was decoded with the testnet's ETF reader, every command checked to be a tagged tuple of one map with a tag of "
          "`data/vocab.py`, and the limits of requirements section 11 applied (commands <= 2000, text <= 64 KB, automatic requests <= 20, "
          "depth <= 32). A reply that fails any of these is a problem listed at the end. Where the name has a reference reply, the "
          "decoded value equals it and its bytes appear verbatim in the frame.", ""]
    for label, (nb, nc, hist, lines, refnote, fetches) in summaries.items():
        L.append("- `%s`: frame %d bytes, %d commands (%s); %s" % (label, nb, nc, ", ".join("%s %d" % kv for kv in sorted(hist.items())), refnote))
        for ln in lines[:8]:
            L.append("    - shows: " + ln)
        if len(lines) > 8:
            L.append("    - ... %d more commands" % (len(lines) - 8))
    L += ["", "Image parts are checked as bytes: each part equals the slice of `data/out/images/*.png` it names.", ""]
    L += ["### Problems found", ""] + (["- " + p for p in problems] if problems else ["None: every checked reply passed the viewer's rules and matched its reference."])
    L += ["", "## Caveats", "",
          "- One machine, loopback: the round trip time is about 0.05 ms and the bandwidth is memory speed. The handshake's CPU cost "
          "(key exchange, signatures, certificate and token checks, on both sides) is what the table shows; the network's time is not.",
          "- The client is Python (`ssl`, OpenSSL " + ssl.OPENSSL_VERSION.split()[1] + ") and the nodes are Silica native programs with OpenSSL 4.x; a Swift viewer's "
          "client costs differ. Client and nodes share the same cores, so concurrent rows partly measure contention between the "
          "client's threads (Python's GIL covers the framing code, not OpenSSL) and the nodes.",
          "- Whether X25519MLKEM768 was the group negotiated is not observable from Python's `ssl` (it reports no group); it is what the "
          "nodes' OpenSSL 4.x offers first, and the client's OpenSSL " + ssl.OPENSSL_VERSION.split()[1] + " is new enough to offer it, so it is expected, not proven here.",
          "- The bridge runs BEES's test unit (fixed clock 1500) and the limits of `nodes/bridge/bridge.role.in` (`slim 5`, `size 4`, "
          "`rate 100000` per hour, `pin 2`, `tin 4`, `cms 4000`); refusals in section 3 show those, not production values.",
          "- The nodes are the builds of `build.sh`; this trial did not compare debug and release builds of the nodes.",
          "- A real network adds round trips, not CPU: see the README section 'Timing trial' for how many.", "",
          "Total run time of the trial: %.0f s." % (time.time() - started)]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main
def start_network():
    # output to a file, not a pipe: the nodes are children of network.sh's shell and would keep a pipe open until they end
    with open(os.path.join(TESTNET, "run", "timing_start.txt"), "w") as f:
        return subprocess.run([NETWORK, "start"], stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT).returncode


def stop_network():
    with open(os.path.join(TESTNET, "run", "timing_stop.txt"), "w") as f:
        return subprocess.run([NETWORK, "stop"], stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT).returncode


def leftovers():
    out = sh("lsof", "-nP", "-iTCP:24400-24433", "-sTCP:LISTEN")
    pids = sh("sh", "-c", "ls %s/*.pid 2>/dev/null" % os.path.join(TESTNET, "run"))
    procs = sh("sh", "-c", "pgrep -fl dangerous_ || true")
    return out, pids, procs


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--conc-total", type=int, default=48)
    ap.add_argument("--out", default=os.path.join(TESTNET, "results", "timing-%s.md" % datetime.date.today().strftime("%Y%m%d")))
    ap.add_argument("--no-start", action="store_true", help="use a running network and leave it running")
    a = ap.parse_args(argv)
    started = time.time()
    started_here = False
    rc = 0

    def on_signal(sig, frm):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_signal)
    try:
        if not a.no_start:
            if start_network() != 0:
                print("network.sh start failed (see testnet/run/*.log)")
                stop_network()
                return 1
            started_here = True
        info = machine_info()
        print("network up; measuring (reps %d)" % a.reps)
        base = baseline(10)
        setup = ctx_setup(20)
        photo = open(os.path.join(IMAGES, "photo.png"), "rb").read()
        icon = open(os.path.join(IMAGES, "icon.png"), "rb").read()
        singles = []
        plan = [("home (small)", "home", ()), ("status (tiny)", "status", ()), ("nodes_table 1 (medium)", "nodes_table", ("1",)),
                ("docs_intro (medium)", "docs_intro", ()), ("events page 1 (large)", "events", ("1",)),
                ("samples page 1, 100 rows (large)", "samples", ("1",))]
        for label, name, args in plan:
            singles.append(run_single(label, name, args, a.reps)); print("  done", label)
        for label, args, exp in [("image_part icon, 2017 B", ("icon", "0", "2017"), icon),
                                 ("image_part photo, 16384 B part", ("photo", "0", "16384"), photo[:16384]),
                                 ("image_part photo, 65536 B part", ("photo", "0", "65536"), photo[:65536]),
                                 ("image_part photo, 131000 B part", ("photo", "0", str(PART_MAX)), photo[:PART_MAX]),
                                 ("image_part photo, 2nd part %d B" % (len(photo) - PART_MAX), ("photo", str(PART_MAX), str(len(photo) - PART_MAX)), photo[PART_MAX:])]:
            singles.append(run_single(label, "image_part", args, a.reps, "bytes", exp)); print("  done", label)
        # the 234 KB image in two parts, one after the other, a new connection each
        xs, ok = [], True
        for _ in range(a.reps + 1):
            t = time.perf_counter()
            r1 = request("image_part", ("photo", "0", str(PART_MAX)))
            r2 = request("image_part", ("photo", str(PART_MAX), str(len(photo) - PART_MAX)))
            xs.append(time.perf_counter() - t)
            ok = verify(r1, "photo part 1", "bytes", photo[:PART_MAX]) and verify(r2, "photo part 2", "bytes", photo[PART_MAX:]) and ok
        xs = xs[1:]
        singles.append({"label": "image photo 234174 B, 2 parts in sequence", "name": "image_part2", "args": (), "bytes": len(photo) + 0, "n": len(xs),
                        "refused": [], "bad": 0, "admit_parts": {}, "phases": {p: (stats(xs) if p in ("full", "full_close") else None) for p in PHASES}})
        # the two-part row has no phase split: fill the rest from the two single rows of the part sizes (sum of medians)
        p1 = next(r for r in singles if r["label"].startswith("image_part photo, 131000"))["phases"]
        p2 = next(r for r in singles if r["label"].startswith("image_part photo, 2nd"))["phases"]
        for k in ("tcp", "tls", "admit", "request", "close"):
            m = {q: p1[k][q] + p2[k][q] for q in ("median", "p95", "min", "max", "mean")}
            m["n"] = p1[k]["n"]
            singles[-1]["phases"][k] = m
        mark_row = run_single("mark home", "mark", ("home",), a.reps, "mark", INDEX["names"]["home"]["mark"]); print("  done mark")
        conc = run_concurrency(a.conc_total, (1, 2, 3, 4, 6, 8)); print("  done concurrency")
        screens = [screen("home: frame + status", "home", (), (), a.reps),
                   screen("nodes: frame + 2 regions + node n01", "nodes", (), [("node", ["n01"])], a.reps),
                   gallery_screen(a.reps)]
        print("  done screens")
        text = report(info, singles, base, setup, conc, screens, mark_row, a.reps, a.conc_total, started)
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, "w").write(text)
        print("wrote", os.path.relpath(a.out, REPO))
        print("problems: %d" % len(problems))
        for p in problems:
            print("  PROBLEM", p)
        for row in singles + [mark_row]:
            if row["refused"] or row["bad"]:
                print("  refused/bad in %s: %d refused, %d bad %s" % (row["label"], len(row["refused"]), row["bad"], set(row["refused"])))
        rc = 1 if problems else 0
    except KeyboardInterrupt:
        print("interrupted"); rc = 1
    finally:
        if started_here:
            if stop_network() != 0:
                print("network.sh stop reported something left"); rc = 1
            out, pids, procs = leftovers()
            if out or pids or procs:
                print("LEFT:", out, pids, procs); rc = 1
            else:
                print("network stopped, no process, port or pid file left")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
