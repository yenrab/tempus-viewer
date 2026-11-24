"""Emits the Silica units, manifests and tables of the testnet's three TRUST nodes and of the bridge, from gen.py's data.

  python3 gen_nodes.py --node content|data|authority --out LEAF_DIR      writes LEAF_DIR/lib/*, LEAF_DIR/trust_whitelist.config
  python3 gen_nodes.py --bridge --out LEAF_DIR                          writes LEAF_DIR/lib/*, edge.spec, bridge.role

Which node serves which name, and with how many arguments, is NODES below (every argument is a byte string, owner ruling OI-17;
a page number is ["2"], image_part is [id, offset, length] as text, a form is a flat list of alternating names and values).
The reply of a name is the gen.py data as a Silica literal, so the bytes the node's `encode((:etf), value)` writes equal
out/replies/NAME.etf (the client checks that for every name and page). Where a reply is a large literal the unit is split
(compile time grows with the square of one string literal, and linearly with the number of literals: measured, see the report).

TEST data about an invented network."""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen
from gen_silica import infer, unify, render, atoms_of, lit

HOST = "127.0.0.1"
# node -> ports (TRUST listener), certificate (BEES's TEST-ONLY n4 certificates) and the functions it serves: (name, arity)
TRUST_NODES = {
    "content": {"port": 24400, "cert": "a",
                "fns": [("home", 0), ("status", 0), ("directory", 0), ("docs_intro", 0), ("docs_commands", 0), ("gallery", 0), ("image_part", 3)]},
    "data": {"port": 24410, "cert": "n",
             "fns": [("nodes", 0), ("nodes_summary", 0), ("nodes_table", 1), ("node", 1), ("events", 1), ("samples", 0), ("samples", 1), ("search", 0),
                     ("search_results", 6), ("live", 0), ("clock", 1), ("slow", 0), ("fail", 0), ("empty", 0)]},
    "authority": {"port": 24420, "cert": "p", "fns": [("mark_of", 1), ("restart_node", 1)]},
}
BRIDGE_ALIAS = {"mark": ("authority", "mark_of")}          # a bridge export that is another node's function
CH = 8192                                                    # hex characters per image chunk literal (4096 bytes)
SLOW_SPIN = 640000000                                        # busy-loop steps of `slow`; calibrated in the run, see run_all
PAGED = {"events": "events", "samples": "samples_page"}      # name -> the function that serves its pages 1..20 (arity 1); samples also has the frame, arity 0
IMPL = {("samples", 1): "samples_page"}                      # Silica function of an export whose name another export shares
UNITS = {                                                    # node -> [(unit, [functions it holds])]
    "content": [("rep_content", ["home", "status", "directory", "docs_intro", "docs_commands", "gallery"]), ("rep_images", ["image_part"])],
    "data": [("rep_data", ["nodes", "nodes_summary", "nodes_table", "node", "search", "search_results", "live", "clock", "slow", "fail", "empty", "samples"]),
             ("rep_events", ["events"])],
    "authority": [("rep_authority", ["mark_of", "restart_node"])],
}


def reply(name, page=None):
    r = gen.REPLIES[name]
    if page is None:
        return r["commands"]
    return r["pages"][page]


def pages_of(name):
    """page text -> commands: events.N and samples.N for N = 1..20 (page 1 of events equals events itself; samples is a frame with no
    arguments and its pages are all table_rows replies)"""
    pg = gen.REPLIES[name]["pages"]
    return {str(p): pg[str(p)] for p in range(1, 21)}


def node_reply_names(node):
    return [n for n, _ in TRUST_NODES[node]["fns"] if n in gen.REPLIES]


def node_data(node):
    """every command list the node can return (for its one type)"""
    out = []
    for n in node_reply_names(node):
        out.append(gen.REPLIES[n]["commands"])
        if n in PAGED:
            out += list(pages_of(n).values())
    return out


def name_data(name):
    out = [gen.REPLIES[name]["commands"]]
    if name in PAGED:
        out += list(pages_of(name).values())
    return out


def name_type(name):
    """one type per name (a sum cannot hold two variants with one tag and two payload types, and docs_commands writes (:code, atom)
    where docs_intro writes (:code, string): reference data, not changed)"""
    ty = None
    for cs in name_data(name):
        ty = unify(ty, infer(cs))
    return ty


def name_atoms(name):
    acc = set()
    atoms_of(name_type(name), acc)
    return acc | {"true", "false"}


def node_atoms(node):
    acc = set()
    for n in node_reply_names(node):
        acc |= name_atoms(n)
    return acc


def all_atoms(tys):
    acc = set()
    for t in tys:
        atoms_of(t, acc)
    return acc | {"true", "false"}


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def atoms_file(path, atoms, why):
    write(path, "# written by gen_nodes.py: %s\n" % why + "\n".join(sorted(atoms)) + "\n")


HEAD = "// Generated by testnet/data/gen_nodes.py from testnet/data/gen.py's data. Do not edit. TEST data about an invented network.\n"
SIG = "(xs: List[string, mem(normal)]) -> (:ok, %s) | (:error, atom)"


def fn_literal(fname, T, cs):
    return ["fn %s() -> %s {" % (fname, T), "    sequence proc[mem(normal)]", "        cs: %s <- %s" % (T, lit(cs)), "    produces pure cs end", "}"]


HELPERS = [
    "fn at(s: string, i: int64) -> int64 {", "    sequence proc[transport]", "        b: int64 <- byte_at(s, i)", "    produces pure b end", "}",
    "fn nibble(b: int64) -> int64 { case b >= 97 of { true -> b - 87; false -> b - 48 } }",
    "fn atoi(s: string, i: int64, acc: int64) -> int64 { case i >= length_bytes(s) of { true -> acc; false -> atoi(s, i + 1, acc * 10 + at(s, i) - 48) } }",
    "fn nth(xs: List[string, mem(normal)], n: int64) -> string {",
    "    case xs of {", "        []: List[string, mem(normal)] -> \"\";",
    "        [h: string, t: List[string, mem(normal)]] -> case n == 0 of { true -> h; false -> nth(t, n - 1) }", "    }", "}",
]


def unit_text(module, body, uses=()):
    return HEAD + "module %s;\nuse bees_atoms;\n" % module + "".join("use %s;\n" % u for u in uses) + "\n" + "\n".join(body) + "\n"


def emit_content_like(node, out):
    """the units of a TRUST node and its manifests"""
    lib = os.path.join(out, "lib")
    fns = dict(TRUST_NODES[node]["fns"])
    trust = ["# written by gen_nodes.py: the functions a peer may name on the %s node" % node]
    natoms = node_atoms(node)
    for unit, names in UNITS[node]:
        exports, body = [], list(HELPERS)
        for name in names:
            exports.append("export %s/1;" % (PAGED[name] if name in PAGED else name))
            if name in PAGED and (name, 0) in TRUST_NODES[node]["fns"]:
                exports.append("export %s/1;" % name)       # the frame (no arguments) has the name; its pages have PAGED[name]
            T = render(name_type(name)) if name in gen.REPLIES else "int64"
            if name == "image_part":
                body += image_part_code(out)
                trust.append("export viewer image_part 3 %s@image_part args string result string" % unit)
            elif name == "mark_of":
                marks = gen.MARKS
                chain = '(:error, bees_atoms@a_unsupported())'
                for n in reversed(sorted(marks)):
                    chain = 'case first(xs) == "%s" of { true -> (:ok, :%s); false -> %s }' % (n, marks[n], chain)
                body += ["fn first(xs: List[string, mem(normal)]) -> string { nth(xs, 0) }",
                         "fn mark_of(xs: List[string, mem(normal)]) -> (:ok, atom) | (:error, atom) { %s }" % chain]
                trust.append("export viewer mark_of 1 %s@mark_of args string result atom" % unit)
            elif name == "fail":
                body.append("fn fail(xs: List[string, mem(normal)]) -> (:ok, %s) | (:error, atom) { (:error, bees_atoms@a_failed()) }" % T)
                trust.append("export viewer fail 0 %s@fail args string result %s" % (unit, T))
            elif name == "slow":
                body += ["fn spin(n: int64, acc: int64) -> int64 { case n <= 0 of { true -> acc; false -> spin(n - 1, acc + 1) } }",
                         "fn slow_after(k: int64, v: %s) -> %s { case k < 0 of { true -> v; false -> v } }" % (T, T)]
                # the delay is a busy loop (Silica has no sleep a worker can call); its result decides whether the reply is returned
                body += fn_literal("slow_reply", T, reply("slow"))
                body.append("fn slow(xs: List[string, mem(normal)]) -> (:ok, %s) | (:error, atom) { (:ok, slow_after(spin(%d, 0), slow_reply())) }" % (T, SLOW_SPIN))
                trust.append("export viewer slow 0 %s@slow args string result %s" % (unit, T))
            elif name in PAGED:
                pg = pages_of(name)
                fname = PAGED[name]
                for p, cs in pg.items():
                    body += fn_literal("%s_p%s" % (name, p), T, cs)
                chain = "(:error, bees_atoms@a_unsupported())"
                for p in sorted(pg, key=int, reverse=True):
                    chain = 'case nth(xs, 0) == "%s" of { true -> (:ok, %s_p%s()); false -> %s }' % (p, name, p, chain)
                body.append("fn %s(xs: List[string, mem(normal)]) -> (:ok, %s) | (:error, atom) { %s }" % (fname, T, chain))
                trust.append("export viewer %s 1 %s@%s args string result %s" % (name, unit, fname, T))
                if (name, 0) in TRUST_NODES[node]["fns"]:
                    body += fn_literal(name + "_r", T, reply(name))
                    body.append("fn %s(xs: List[string, mem(normal)]) -> (:ok, %s) | (:error, atom) { (:ok, %s_r()) }" % (name, T, name))
                    trust.append("export viewer %s 0 %s@%s args string result %s" % (name, unit, name, T))
            else:
                body += fn_literal(name + "_r", T, reply(name))
                body.append("fn %s(xs: List[string, mem(normal)]) -> (:ok, %s) | (:error, atom) { (:ok, %s_r()) }" % (name, T, name))
                trust.append("export viewer %s %d %s@%s args string result %s" % (name, fns[name], unit, name, T))
        text = unit_text(unit, exports + [""] + body)
        write(os.path.join(lib, unit + ".silica"), text)
        # the unit writes the tags and keys of its type as literals: its own manifest (D30)
        atoms_file(os.path.join(lib, unit + ".atoms"), natoms | ({"look_only", "does_something"} if "mark_of" in names else set()) | {"failed"}, "tags and keys of the reply type")
    marks_atoms = {"look_only", "does_something"} if node == "authority" else set()
    atoms_file(os.path.join(lib, "bees_trust_mfa.atoms"), natoms | marks_atoms, "the generated MFA table writes the reply type")
    names = {"viewer", "failed"} | {n for n, _ in TRUST_NODES[node]["fns"]} | marks_atoms
    atoms_file(os.path.join(lib, "node_names.atoms"), names, "the module and function names a peer may send")
    write(os.path.join(lib, "node.trust"), "\n".join(trust) + "\n")
    # the whitelist (read at build time): the bridge's TRUST certificate (b.pem) is the only peer, for these functions only
    perm = ", ".join("{%s, %d}" % (n, a) for n, a in TRUST_NODES[node]["fns"])
    write(os.path.join(out, "trust_whitelist.config"),
          "%% the bridge's TRUST certificate (b.pem of BEES's test-only certificates) is the only peer; it may call these functions only\n"
          "#{\n  \"b.pem\" => [{viewer, [%s]}]\n}.\n" % perm)


def image_part_code(out):
    """image_part(id, offset, length): the byte range of out/images/ID.png, from hex chunk literals (see the report for why)"""
    L = []
    imgs = {}
    for k in ("icon", "chart", "photo"):
        imgs[k] = open(os.path.join(HERE, "out", "images", k + ".png"), "rb").read()
    chunk_fns = {}
    for k, b in imgs.items():
        h = b.hex()
        for i in range(0, len(h), CH):
            n = "img_%s_%d" % (k, i // CH)
            L.append('fn %s() -> string { "%s" }' % (n, h[i:i + CH]))
            chunk_fns.setdefault(k, []).append(n)
    def chunk_case(k):
        e = '""'
        for i, n in reversed(list(enumerate(chunk_fns[k]))):
            e = "case i == %d of { true -> %s(); false -> %s }" % (i, n, e)
        return e
    ch = '""'
    for k in imgs:
        ch = 'case id == "%s" of { true -> %s; false -> %s }' % (k, chunk_case(k), ch)
    size = "0 - 1"
    for k, b in imgs.items():
        size = 'case id == "%s" of { true -> %d; false -> %s }' % (k, len(b), size)
    L += ["fn img_chunk(id: string, i: int64) -> string { %s }" % ch,
          "fn img_size(id: string) -> int64 { %s }" % size,
          # hex characters [hs, he) of the image's hex text, piece by piece across the chunk literals
          "fn hexrange(id: string, hs: int64, he: int64) -> string {",
          "    case hs >= he of {", "        true -> \"\";",
          "        false -> {",
          "            k: int64 <- hs / %d;" % CH,
          "            e1: int64 <- case he < (k + 1) * %d of { true -> he; false -> (k + 1) * %d };" % (CH, CH),
          "            concat(substring(img_chunk(id, k), hs - k * %d, e1 - k * %d), hexrange(id, e1, he))" % (CH, CH),
          "        }", "    }", "}",
          "fn pairs(s: string, i: int64, acc: List[int64, mem(normal)]) -> List[int64, mem(normal)] {",
          "    case i < 0 of {", "        true -> acc;", "        false -> {",
          "            v: int64 <- nibble(at(s, i)) * 16 + nibble(at(s, i + 1));",
          "            j: int64 <- i - 2;", "            sequence proc[mem(normal)]",
          "                nxt: List[int64, mem(normal)] <- prepend[int64, mem(normal)](v, acc)",
          "            produces pure pairs(s, j, nxt) end", "        }", "    }", "}",
          "fn unhex(s: string) -> string {", "    sequence proc[mem(normal), transport]",
          "        e: List[int64, mem(normal)] <- empty[int64, mem(normal)]();",
          "        xs: List[int64, mem(normal)] <- pairs(s, length_bytes(s) - 2, e);",
          "        out: string <- bytes_of(xs)", "    produces pure out end", "}",
          "fn part(id: string, off: int64, len: int64) -> (:ok, string) | (:error, atom) {",
          "    case off < 0 or len < 0 or off + len > img_size(id) of {",
          "        true -> (:error, bees_atoms@a_unsupported());",
          "        false -> (:ok, unhex(hexrange(id, off * 2, (off + len) * 2)))",
          "    }", "}",
          "fn image_part(xs: List[string, mem(normal)]) -> (:ok, string) | (:error, atom) { part(nth(xs, 0), atoi(nth(xs, 1), 0, 0), atoi(nth(xs, 2), 0, 0)) }"]
    return L


def emit_bridge(out):
    lib = os.path.join(out, "lib")
    exports = []                       # (viewer name, arity, node, remote name)
    for node, d in TRUST_NODES.items():
        for n, a in d["fns"]:
            if n == "mark_of":
                continue
            exports.append((n, a, node, n))
    exports.append(("mark", 1, "authority", "mark_of"))
    body, trust, spec = [], ["# written by gen_nodes.py: the functions an edge may name on this bridge (stubs: the bridge runs none of them)"], []
    seen = set()
    for n, a, node, r in exports:
        impl = IMPL.get((n, a), n)
        body.append("fn %s(xs: List[string, mem(normal)]) -> (:ok, int64) | (:error, atom) { (:ok, 0) }" % impl)
        trust.append("export viewer %s %d bridge_fns@%s args string result int64" % (n, a, impl))
        spec.append("{%s, %d}" % (n, a))
    write(os.path.join(lib, "bridge_fns.silica"), HEAD + "// the types of the MFA table only: the application (bridge.role) answers every request\nmodule bridge_fns;\nuse bees_atoms;\n\n"
          + "".join("export %s/1;\n" % IMPL.get((n, a), n) for n, a, *_ in exports) + "\n" + "\n".join(body) + "\n")
    write(os.path.join(lib, "bridge_fns.trust"), "\n".join(trust) + "\n")
    write(os.path.join(out, "edge.spec"), "# written by gen_nodes.py: what a tempus_edge may call (design 17.4: none by default)\ntype tempus_edge [{viewer, [%s]}]\n" % ", ".join(spec))
    allnames = [n for node in TRUST_NODES for n in node_reply_names(node)]
    base = set()
    for n in allnames:
        base |= name_atoms(n)
    # the TRUST client's reading of a result frame holds an atom only when the program's table has it (bees_trust_frame@atom_held)
    atoms = base | {"look_only", "does_something", "viewer"} | {n for n, *_ in exports} | {r for *_, r in exports}
    atoms_file(os.path.join(lib, "node_names.atoms"), atoms, "names an edge may call, and every atom a reply of any node may carry (the bridge reads result frames)")
    # the application's routing
    addr = {n: "%s:%d" % (HOST, d["port"]) for n, d in TRUST_NODES.items()}
    chain = "{ sequence _: boolean <- bees_tempus_bridge@rq_fail(rq, \"no such function here\") produces pure s end }"
    for n, a, node, r in reversed(exports):
        chain = 'case mt == "viewer:%s/%d" of { true -> fwd(s, rq, "%s", bees_atoms@a_viewer(), bees_atoms@a_%s(), %d, args); false -> %s }' % (n, a, addr[node], r, a, chain)
    tpl = open(os.path.join(out, "bridge.role.in")).read()
    write(os.path.join(out, "bridge.role"), tpl.replace("//@ON_CALL@", "fn on_call(s: $BA$, _me: actor_ref, args: string, mt: string, rq: actor_ref) -> $BA$ {\n    %s\n}" % chain))
    json.dump({"exports": exports}, open(os.path.join(out, ".exports.json"), "w"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", choices=list(TRUST_NODES))
    ap.add_argument("--bridge", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.bridge:
        emit_bridge(a.out)
    else:
        emit_content_like(a.node, a.out)


if __name__ == "__main__":
    main()
