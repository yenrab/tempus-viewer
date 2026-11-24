"""Generates the testnet's data and reference replies. Deterministic: the same seed gives the same bytes.

  python3 gen.py            writes out/replies/*.etf (+ .txt), out/images/*.png, out/cases/*.etf, out/index.json
  python3 gen.py --check    regenerates in memory and compares with out/ (a test that nothing drifted)

Everything here is TEST data about an invented network. The vocabulary is provisional (vocab.py)."""
import json, os, random, struct, sys, zlib
from etf import Atom as A, enc, dec, show
import vocab as v

SEED = 481
HOST = "127.0.0.1:481"                      # the default port ruled for tempus:// is 481
FRAME_MAX = 131072
LIMITS = {"commands": 2000, "depth": 32, "text": 65536}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

rng = random.Random(SEED)
def addr(name, *args):
    q = "".join(f"{'?' if i == 0 else '&'}a{i}={a}" for i, a in enumerate(args))
    return f"tempus://{HOST}/{name}{q}"

# ---- the invented network ---------------------------------------------------------------------------------------
ROLES = ["bridge", "trust", "tempus_sentinel", "tempus_edge"]
NODES = []
for i in range(1, 41):
    role = ROLES[(i - 1) % 4] if i > 4 else ROLES[i - 1]
    NODES.append({"id": f"n{i:02d}", "name": f"{role.split('_')[-1]}-{i:02d}", "role": role,
                  "status": rng.choices(["up", "degraded", "down"], [80, 14, 6])[0],
                  "load": rng.randint(2, 97), "uptime_h": rng.randint(1, 5000), "port": 24000 + i})
EVENT_KINDS = [("info", "peer admitted"), ("info", "shuffle complete"), ("warn", "token expires soon"),
               ("warn", "slow reply"), ("error", "connection refused"), ("info", "view merged"), ("error", "bad frame")]
EVENTS = []
for i in range(1, 1001):
    lvl, msg = rng.choice(EVENT_KINDS)
    n = rng.choice(NODES)
    EVENTS.append({"n": i, "level": lvl, "node": n["id"], "msg": msg, "at": 1790000000 + i * 17})
SAMPLES = [[str(i), f"s{rng.randint(1000, 9999)}", f"{rng.uniform(0, 100):.3f}", f"{rng.uniform(-5, 5):+.2f}",
            str(1790000000 + i * 60)] for i in range(1, 2001)]

# ---- images (PNG written with the standard library) ---------------------------------------------------------------
def png(w, h, pixel):
    raw = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
_noise = random.Random(SEED + 1)
IMAGES = {
    "icon":  (32, 32, "A small blue-green gradient square, the network's icon", png(32, 32, lambda x, y: (20, 80 + x * 4, 140 + y * 3))),
    "chart": (320, 200, "A bar chart of load: eight bars of rising height", png(320, 200, lambda x, y: (40, 120, 200) if (x // 40) % 2 == 0 and y > 190 - (x // 40 + 1) * 20 else (245, 245, 245))),
    "photo": (400, 400, "A grey noise field used to test large images", png(400, 400, lambda x, y: (lambda g: (g, g, g))(_noise.randint(0, 255)))),
}

# ---- the reply for each published name ---------------------------------------------------------------------------
MARKS = {}
REPLIES = {}
def publish(name, mark, commands, doc=""):
    assert mark in ("look_only", "does_something")
    MARKS[name] = mark
    REPLIES[name] = {"commands": [v.vocabulary()] + commands, "doc": doc}

def table_of_nodes(into, nodes):
    return v.table(into, "Nodes", ["id", "name", "role", "status", "load %", "uptime h"],
                   [[n["id"], n["name"], n["role"], n["status"], str(n["load"]), str(n["uptime_h"])] for n in nodes])

publish("home", "look_only", [
    v.title("Test network"), v.language("en"), v.keep(30),
    v.heading("main", 1, "Test network"),
    v.paragraph("main", "An invented network of ", v.strong("forty nodes"), " used to try the viewer. See the ",
                v.link("directory", addr("directory")), " or read the ", v.link("introduction", addr("docs_intro")), "."),
    v.region("main", "status"),
    v.fetch("status", "status"),
    v.listing("main", [[v.link("Nodes", addr("nodes"))], [v.link("Events", addr("events", "1"))],
                       [v.link("Search", addr("search"))], [v.link("Gallery", addr("gallery"))],
                       [v.link("Samples", addr("samples", "1"))], [v.link("Live clock", addr("live"))]]),
], "the first screen; one region filled by a second request")

up = sum(1 for n in NODES if n["status"] == "up")
publish("status", "look_only", [
    v.paragraph("status", f"{up} of {len(NODES)} nodes are up.")], "a reply that fills the region named in home")

publish("nodes", "look_only", [
    v.title("Nodes"), v.language("en"), v.keep(10),
    v.heading("main", 1, "Nodes"), v.region("main", "summary"), v.region("main", "table"),
    v.fetch("summary", "nodes_summary"), v.fetch("table", "nodes_table", "1"),
], "a frame of two regions, each filled by its own request")
publish("nodes_summary", "look_only", [
    v.listing("summary", [f"{s}: {sum(1 for n in NODES if n['status'] == s)}" for s in ("up", "degraded", "down")])])
publish("nodes_table", "look_only", [v.clear("table"), table_of_nodes("table", NODES),
    v.button("table", "Open the first node", "node", NODES[0]["id"])], "a table of forty rows")

publish("node", "look_only", [
    v.heading("main", 1, "Node n01"),
    v.table("main", "Details", ["field", "value"], [["id", NODES[0]["id"]], ["role", NODES[0]["role"]],
            ["status", NODES[0]["status"]], ["port", str(NODES[0]["port"])]]),
    v.button("main", "Restart this node", "restart_node", NODES[0]["id"]),
], "node detail; the button names a does-something request")
publish("restart_node", "does_something", [
    v.paragraph("main", v.strong("Restart requested"), " for node n01. (Nothing restarts: this is test data.)")],
    "an acting request: must not run from an outside link")

def event_page(p, size=50):
    rows = [[str(e["n"]), str(e["at"]), e["level"], e["node"], e["msg"]] for e in EVENTS[(p - 1) * size:p * size]]
    last = (len(EVENTS) + size - 1) // size
    cmds = [v.heading("main", 1, f"Events, page {p} of {last}"),
            v.table("main", "Event log", ["#", "time", "level", "node", "message"], rows)]
    if p > 1: cmds.append(v.block_link("main", "Previous page", addr("events", str(p - 1))))
    if p < last: cmds.append(v.block_link("main", "Next page", addr("events", str(p + 1))))
    return cmds
publish("events", "look_only", event_page(1), "page 1 of the event log; other pages take the page number as the argument")
REPLIES["events"]["pages"] = {str(p): [v.vocabulary()] + event_page(p) for p in range(1, 21)}

publish("directory", "look_only", [
    v.heading("main", 1, "Directory"),
    v.listing("main", [[v.link(n, addr(n, *a))] for n, a in [("home", ()), ("nodes", ()), ("events", ("1",)), ("search", ()),
                                                            ("gallery", ()), ("samples", ("1",)), ("live", ()), ("docs_intro", ()),
                                                            ("docs_commands", ())]], ordered=True)])

def prose(n):
    s = ["A viewer asks a node for commands and shows what they describe.", "No reply holds code.",
         "The viewer decides how every thing looks.", "A screen may be built from several requests.",
         "A pass is signed for one key.", "Only tempus links are followed.", "Each region is filled by its own reply."]
    return " ".join(rng.choice(s) for _ in range(n))
publish("docs_intro", "look_only", [
    v.title("Introduction"), v.language("en"), v.keep(300),
    v.heading("main", 1, "Introduction"), v.paragraph("main", prose(5)),
    v.heading("main", 2, "What a command is"), v.paragraph("main", prose(4), v.code(" {heading, #{...}} ")),
    v.quotation("main", "The viewer decides how it looks.", "design notes"),
    v.rule("main"), v.heading("main", 2, "A list"), v.listing("main", [prose(1), prose(1), prose(2)]),
    v.heading("main", 2, "Steps"), v.listing("main", ["Add the network.", "Open an address.", "Read the screen."], ordered=True),
    v.preformatted("main", "tempus://" + HOST + "/home"),
])
publish("docs_commands", "look_only", [v.heading("main", 1, "Commands"), v.paragraph("main", "Every command in vocabulary v0:"),
    v.listing("main", [[v.code(t)] for t in sorted({c[0] for r in REPLIES.values() if r for c in r["commands"]})])])

publish("search", "look_only", [
    v.heading("main", 1, "Search"),
    v.form("main", "q", [v.field_text("q", "Words to look for"),
                          v.field_choice("scope", "Where", [("nodes", "Nodes"), ("events", "Events"), ("all", "Everything")], "all"),
                          v.field_tick("exact", "Whole words only")], "Search", "search_results")])
publish("search_results", "look_only", [
    v.heading("main", 2, "Results"),
    v.table("main", "Matches", ["kind", "id", "text"], [["node", n["id"], n["name"]] for n in NODES[:5]])],
    "the reply to the form: the form's fields arrive as one map argument")

publish("gallery", "look_only", [
    v.heading("main", 1, "Gallery"),
    *[v.image("main", k, alt, w, h, len(b)) for k, (w, h, alt, b) in IMAGES.items()],
], "three images; the large one is above one frame and is fetched in parts by image_part")

publish("samples", "look_only", [
    v.heading("main", 1, "Samples"), v.region("main", "rows"),
    v.table("rows", "Samples, rows 1 to 100", ["#", "name", "value", "delta", "time"], SAMPLES[:100]),
    v.fetch("main", "samples", "2")], "a table of 2000 rows in pages of 100")
REPLIES["samples"]["pages"] = {str(p): [v.vocabulary(), v.table_rows("rows", SAMPLES[(p - 1) * 100:p * 100])] for p in range(1, 21)}

publish("live", "look_only", [
    v.heading("main", 1, "Live clock"), v.region("main", "clock"), v.fetch("clock", "clock", "0"),
    v.refresh("clock", 5, "clock", "1")], "a region refreshed every 5 seconds by a request")
publish("clock", "look_only", [v.clear("clock"), v.paragraph("clock", "tick 0")])
publish("fail", "look_only", [], "the function fails: the viewer sees only 'could not be fetched'")
publish("empty", "look_only", [], "a valid reply with no commands")
publish("slow", "look_only", [v.paragraph("main", "Answered after a delay.")], "a node that answers after a delay")

# ---- reference replies with a verdict, valid and invalid (the conformance set, first draft) ------------------------
CASES = []
def case(name, term, verdict, why, raw=None):
    CASES.append({"name": name, "verdict": verdict, "why": why, "term": term, "raw": raw})
okc = [v.vocabulary()]
case("minimal", okc, "accept", "a reply that only states its version")
case("every_display_command", REPLIES["docs_intro"]["commands"], "accept", "headings, runs, lists, quotation, rule, preformatted")
case("form_and_table", REPLIES["search"]["commands"] + REPLIES["nodes_table"]["commands"][1:], "accept", "a form with three field kinds and a table")
case("exact_text_limit", okc + [v.paragraph("main", "x" * LIMITS["text"])], "accept", "text of exactly 64 KB, the limit")
case("exact_command_limit", okc + [v.rule("main")] * (LIMITS["commands"] - 1), "accept", "exactly 2000 commands, the limit")
def nest(d):
    cs, prev = [], "main"
    for i in range(d):
        cs.append(v.region(prev, f"r{i}")); prev = f"r{i}"
    return cs
case("exact_depth_limit", okc + nest(LIMITS["depth"]), "accept", "regions nested exactly 32 deep, the limit")
case("fallback_used", okc + [(A("chart3d"), {"into": "main", "fallback": [v.paragraph("main", "A chart is not shown.")]})],
     "use_fallback", "an unknown display command with the author's fallback (6.1.3)")
case("unknown_display_no_fallback", okc + [(A("sparkle"), {"into": "main"}), v.paragraph("main", "after")],
     "skip_with_note", "an unknown display command without a fallback is skipped with a visible note (6.1.3)")
case("unknown_action", okc + [(A("exec"), {"program": "x"})], "refuse_reply", "an unknown action command refuses the whole reply (6.1.3)")
case("newer_version", [(A("vocabulary"), {"version": v.VERSION + 1}), v.rule("main")], "refuse_reply", "a version newer than the viewer's (6.1.3)")
case("no_version", [v.rule("main")], "refuse_reply", "a reply must state its vocabulary version (6.4)")
case("text_too_long", okc + [v.paragraph("main", "x" * (LIMITS["text"] + 1))], "refuse_reply", "text over 64 KB (11)")
case("too_many_commands", okc + [v.rule("main")] * LIMITS["commands"], "refuse_reply", "2001 commands (11)")
case("too_deep", okc + nest(LIMITS["depth"] + 1), "refuse_reply", "regions nested 33 deep (11)")
case("image_without_alt", okc + [v.image("main", "icon", "", 32, 32, 100)], "refuse_command", "an image needs a text description (10.1)")
case("field_without_label", okc + [v.form("main", "q", [v.field_text("q", "")], "Go", "search_results")], "refuse_command", "a field needs a label (10.1)")
case("link_not_tempus", okc + [v.block_link("main", "elsewhere", "https://example.com/")], "refuse_command", "only tempus:// links exist (3.1)")
case("not_a_list", {"a": 1}, "refuse_reply", "a reply is a list of commands", None)
case("untagged_command", okc + [b"heading"], "refuse_reply", "a command is a tagged tuple carrying a map")
case("pid_in_reply", None, "refuse_reply", "a process identifier is not data (6.1.1); bytes made by Erlang term_to_binary of {rule, #{who => Pid}}",
     raw=bytes.fromhex("836c000000026802770a766f636162756c6172797400000001770776657273696f6e61016802770472756c6574000000027704696e746f6d000000046d61696e770377686f58770d6e6f6e6f6465406e6f686f73740000000500000000000000006a"))

# ---- write -------------------------------------------------------------------------------------------------------
def build():
    files = {}
    index = {"seed": SEED, "host": HOST, "frame_max": FRAME_MAX, "limits": LIMITS, "vocabulary": v.VERSION, "names": {}, "cases": [], "images": {}}
    for name, r in REPLIES.items():
        if not r: continue
        terms = {name: r["commands"]}
        for k, cs in (r.get("pages") or {}).items():
            terms[f"{name}.{k}"] = cs
        for fname, cs in terms.items():
            b = enc(cs)
            assert len(b) <= FRAME_MAX, (fname, len(b))
            files[f"replies/{fname}.etf"] = b
            files[f"replies/{fname}.txt"] = (show(cs) + "\n").encode()
        index["names"][name] = {"mark": MARKS[name], "bytes": len(enc(r["commands"])), "doc": r["doc"],
                                "pages": sorted((r.get("pages") or {}).keys(), key=int)}
    for c in CASES:
        b = c["raw"] if c["raw"] is not None else enc(c["term"])
        files[f"cases/{c['name']}.etf"] = b
        index["cases"].append({"name": c["name"], "verdict": c["verdict"], "why": c["why"], "bytes": len(b)})
    for k, (w, h, alt, b) in IMAGES.items():
        files[f"images/{k}.png"] = b
        index["images"][k] = {"width": w, "height": h, "alt": alt, "bytes": len(b), "parts_of_frame": -(-len(b) // FRAME_MAX)}
    files["index.json"] = (json.dumps(index, indent=1, sort_keys=True) + "\n").encode()
    return files

if __name__ == "__main__":
    files = build()
    if "--check" in sys.argv:
        bad = [p for p, b in files.items() if not os.path.exists(os.path.join(OUT, p)) or open(os.path.join(OUT, p), "rb").read() != b]
        extra = [os.path.relpath(os.path.join(d, f), OUT) for d, _, fs in os.walk(OUT) for f in fs
                 if os.path.relpath(os.path.join(d, f), OUT) not in files]
        print("PASS  out/ is what gen.py writes" if not bad and not extra else f"FAIL  differs: {bad[:5]} extra: {extra[:5]}")
        sys.exit(1 if bad or extra else 0)
    import shutil
    shutil.rmtree(OUT, ignore_errors=True)
    for p, b in files.items():
        full = os.path.join(OUT, p); os.makedirs(os.path.dirname(full), exist_ok=True); open(full, "wb").write(b)
    print(f"wrote {len(files)} files to {OUT}")
