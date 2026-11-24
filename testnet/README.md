# Test network

A network built from [BEES](https://github.com/Silica-Language-and-Compiler/project-bees) and the Silica compiler for
the viewer to run against: one bridge, several TRUST nodes and several TEMPUS nodes, serving generated data.
Requirements: `TEMPUS-viewer-requirements.md`, section 14.5. Everything here is TEST data about an invented network, and
the keys and passes are BEES's test-only ones.

Status (2026-11-24): the data and the reference replies exist and are checked. The first slice runs: a client calls
`viewer:home/0` through the bridge, the bridge routes it to the content node, and the decoded result equals
`data/out/replies/home.etf` (the reference bytes appear verbatim in the result frame). Stage 2 followed: all 20 published names and every page are served through the bridge from three TRUST nodes and
checked against the reference bytes (`testnet/run_all.sh`: 93 checks, all pass). Stage 3 added a sentinel and three edges, and
`testnet/network.sh` (start, status, stop); `run_all.sh` now starts the whole network, runs the 93 checks and 50 more on the TEMPUS nodes, and
stops it (see Stage 3).

## What exists

- `data/`: a generator (`gen.py`) for the data sets and reference replies, a small ETF writer (`etf.py`) and its tests
  (`test_etf.py`, `erl_check.escript`). Run `python3 gen.py` to write `out/`, `python3 gen.py --check` to confirm that
  `out/` is what the generator writes, `python3 test_etf.py` for the encoder checks. The seed is 481, so every run gives
  the same bytes.
- `experiments/etf-commands/`: a Silica function that returns a mixed list of commands, encoded as ETF by Silica and
  decoded by stock Erlang. It settled the form of a command (below).

## The data

20 published names (`out/index.json` lists each with its mark, size and pages):

| Names | What it exercises |
|---|---|
| `home`, `status` | a first screen with a region filled by a second request |
| `nodes`, `nodes_summary`, `nodes_table`, `node` | a frame of regions, each filled by its own request; a 40-row table; a detail table |
| `events` (20 pages), `samples` (20 pages) | paging: a 1000-row log and a 2000-row table in pages of 50 and 100 |
| `docs_intro`, `docs_commands`, `directory` | headings, runs (plain, emphasis, strong, code, link), lists, quotation, rule, preformatted text |
| `search`, `search_results` | a form with a text field, a choice field and a tick box, and the reply to it |
| `gallery` | three images: 2 KB, 0.9 KB and 234 KB; the last is above one frame (131072) and needs two parts |
| `live`, `clock` | a region refreshed every 5 seconds |
| `restart_node` | the one `does_something` name; the rest are `look_only` |
| `fail`, `empty`, `slow` | a failing function, a reply with no commands, a late reply |

`out/cases/` holds 20 reference replies with the verdict a viewer must reach (accept, use the fallback, skip with a
note, refuse the command, refuse the whole reply): the limits at their exact values and one over, an unknown action
and an unknown display command, a newer version, a missing version, an image with no description, a field with no
label, a link that is not `tempus://`, a reply that is not a list, an untagged command, and a process identifier. This
is a first draft of the conformance set (requirement 14.1).

## Findings that shaped the data

1. **A command cannot be a bare map in Silica.** A sum may hold at most one record variant (spec, wire rules; error
   E2404), so a mixed list of commands cannot be a list of maps. A tagged tuple carrying one map works: `{heading,
   #{into => ..., level => 1, text => ...}}`. The vocabulary here (`vocab.py`) uses that form, provisionally. This
   changed the form that BQ-2 recommended; the owner ruled for the tagged tuple on 2026-11-24 (OI-16).
2. **Request arguments are one element type.** A TRUST export declares `args <ElemType>`, a list of one type. The
   owner ruled on 2026-11-24 that every argument is a byte string, a number or true/false written as text and a form sent
   as a flat list of alternating names and values (OI-17).
3. **Silica writes map keys in alphabetical order.** The generator does the same, so its bytes equal Silica's. A
   reader must not depend on key order.
4. **The release compiler does not carry the standard library units** (`wire_etf`, `Supervisor`, `Carrier`, ...). Their
   sources come from the Silica repository at the release tag's commit, as BEES does by symbolic link (OI-18, accepted).

## The first slice

    SILICA_COMPILER=<release compiler> BEES_ROOT=<scratch clone of project-bees> SILICA_ROOT=<scratch clone of silica> testnet/build.sh
    testnet/run_slice.sh

`build.sh` clones the two public repositories where it is told, checks Silica out at the release commit
(`e53689ec96c92699fc996a006762d40fcc288680`) and aborts if it is anywhere else, builds the natives, the content node
(`nodes/content`, TRUST), the bridge (`nodes/bridge`, TEMPUS + TRUST client), and `nodes/replycheck`, which runs the
content node's own entry without a network and compares its bytes with the reference. `run_slice.sh` starts the two
nodes, calls `viewer:home/0` with `nodes/client/call_home.py` and stops them. The compiler must be passed on the make
command line, because BEES's `silica.mk` ignores the environment variable. With the standard library taken from a local
branch instead of the release commit, TLS never completed (OI-18). Ports: content TRUST 24400, bridge TEMPUS 24401.

Found on the way: a TRUST frame is refused (`unknown_atom`) if it carries an atom missing from the program's atom table,
so `true` and `false` must be in it (the generator adds them); and BEES's Python client cannot decode the tuples of a
reply, so the script reads the raw frame bytes (OI-19).

## Stage 2: all names, three TRUST nodes, the mark query

    testnet/build.sh        (same environment as for the first slice)
    testnet/run_all.sh

| Node | TRUST port | Serves |
|---|---|---|
| `content` | 24400 | home, status, directory, docs_intro, docs_commands, gallery, image_part |
| `data` | 24410 | nodes, nodes_summary, nodes_table, node, events (20 pages), samples (frame and 20 pages), search, search_results, live, clock, slow, fail, empty |
| `authority` | 24420 | `mark_of`, `restart_node` |
| `bridge` | TEMPUS 24401 | every `viewer:` name, routed onward; its own TRUST side is configured on 24406 and nothing listens |

`run_all.sh` calls every name and every page through the bridge and compares the decoded value and the verbatim bytes with
`data/out/replies`; asks `viewer:mark` for all 20 names and compares with `index.json`; and checks that `fail` and a
refusal look the same to the client, that `slow` answers within the window, that an unexported name and a wrong arity
are refused, and that `image_part` serves the 234 KB photo in two parts.

- **The mark query is a stand-in.** `viewer:mark/1` takes the name and the bridge asks `authority` (`mark_of/1`). The real
  form is still an open BEES-side question (OI-3).
- **Images** are embedded as 8192-hex-character chunk literals, because one 468 KB literal did not finish compiling
  (compile time is roughly quadratic in the size of a single literal and linear across literals).
- **`slow`** is a busy loop (Silica has no sleep a worker can call), so its delay is machine dependent: 1.4 to 1.5 s here.
- **The largest part of an image** that fits one frame is about 131000 bytes, not 131072.
- **A field called `bytes` cannot be used** in a Silica record (reserved word, E1069), so the image command's size is `size`.
- The bridge's per-peer request limit was raised from BEES's 20 an hour to 100000 for the checks; build times are about
  3.5 minutes in all.

## Plan for the nodes

Topology (ports are provisional; the bridge's TEMPUS port is the default, 481):

| Node | Kind | Job |
|---|---|---|
| `bridge` | TEMPUS bridge + TRUST client | the viewer's host (`127.0.0.1:481`); routes each published name to a TRUST node |
| `content` | TRUST | `home`, `status`, `directory`, `docs_*`, `gallery`, `image_part` |
| `data` | TRUST | `nodes*`, `node`, `events`, `samples`, `search*`, `live`, `clock`, `slow`, `fail`, `empty` |
| `authority` | TRUST | decides each name's mark (`look_only` or `does_something`) and runs `restart_node` |
| `sentinel`, `edge1`, `edge2`, `edge3` | TEMPUS | a gossip network around the bridge, so the viewer talks to a real network (ports 24430 to 24433, see Stage 3) |

Steps, each with a trial and a golden as BEES does (steps 1 to 4 are done, and the script of step 5; the command-line timing
trial of step 5 remains):

1. Generate Silica for the replies: one typed vocabulary type (a sum of tagged tuples) and one builder per reply, with
   the large tables built from the same seeded generator in Silica (not literals), and a check that a node's reply bytes
   equal `out/replies/*.etf`.
2. One TRUST node and one bridge answering `home`. A Python or Swift client calls it and compares the reply with the
   reference.
3. Add `content`, `data` and `authority`, the routing in the bridge, and the mark query (requirement 5.11).
4. Add the TEMPUS nodes. Done (Stage 3).
5. A script that starts the whole network and stops it (done: `network.sh`), and a trial that runs the command-line timing test against it (open).

## Stage 3: the TEMPUS nodes, and one script for the whole network

    testnet/build.sh                 (builds the new leaf nodes/tempus as well; the same environment as before)
    testnet/network.sh start|status|stop
    testnet/run_all.sh               (starts the network, runs both check scripts, stops it; --keep leaves it running)

| Node | Port | Role | Identity (BEES's TEST-ONLY) | Joins through |
|---|---|---|---|---|
| `authority` | TRUST 24420 | marks, `restart_node` | | |
| `content` | TRUST 24400 | home, status, docs, gallery | | |
| `data` | TRUST 24410 | tables, events, samples, search, live, clock | | |
| `sentinel` | TEMPUS 24430 | sentinel (token type `tempus_sentinel`) | 2, certificate `sentinel` | none: the first sentinel |
| `edge1`, `edge2`, `edge3` | TEMPUS 24431, 24432, 24433 | edge (token type `tempus_edge`) | 0 `node`, 5 `x2`, 6 `x3` | the sentinel |
| `bridge` | TEMPUS 24401 (TRUST client side 24406, nothing listens) | bridge, as before | 3 `bridge` | the sentinel (new) |

`nodes/tempus` builds the four new programs from one leaf, as BEES's `trials/t3_tempus_nodes` does: the generator
`tools/bees_tempus_gen.py edge` makes each root unit from the node part, the link edge, the carrier edge, the shared application
`node.role` and one role file per node (`sentinel.role`, `edge1.role` ...: identity number, token type, port, sentinels). They are
TEMPUS nodes only, with no TRUST side. The bridge now also joins through the sentinel (`sents` in `bridge.role.in`, port 24430) and its
whitelist lists the sentinel's certificate; the bridge's checks and `viewer:` routing are unchanged.

`network.sh start` starts the nodes in this order: authority, content, data, sentinel, edge1, edge2, edge3, bridge (a node that dials
another comes after it), waits for each to be ready (a TRUST node prints `listening`, a TEMPUS node that joins prints `join: done`),
and prints the table of `status`. Each node's standard input is a named pipe (`run/NAME.in`) that the node holds open for reading and
writing, and its output goes to `run/NAME.log`; `run/NAME.pid` holds the process number. `stop` writes `exit` to each pipe in the
reverse order (the way BEES's runners end a node), waits up to 20 s for it and only then ends the process, removes the pid files and
pipes, and checks that no port is left open. `start` refuses when a node of the network runs or one of the ports is taken; `status`
exits 1 unless all eight nodes run and listen. It uses no `rm -r`.

`nodes/client/run_tempus.py` (50 checks, run by `run_all.sh` after the 93) shows, from outside and with BEES's own Python client, that
each TEMPUS node is up and does its role. A `sample` request returns entries of one of a node's three stores, so what each node has
learned can be seen on the wire:

| Group | What it proves |
|---|---|
| up | each of the five nodes admits a client (TLS 1.3, token, proof of possession) and its descriptor names its own peer id and token type |
| admission | an expired token and a token another producer signed are refused by all five; an edge token on a whitelisted certificate and a bridge token on a certificate that is not listed are refused; a bridge-typed client with a whitelisted certificate is admitted by the sentinel |
| join | after the start the sentinel holds the three edges and the bridge; the bridge learned the three edges; every node holds the sentinel; edge2 holds edge1, edge3 holds both, edge1 (the first) holds none |
| gossip | a tick of edge1's edge store makes it learn edges from the sentinel; a tick of each edge's bridge store makes it learn the bridge; a tick of edge3's edge store and of the bridge's edge store each makes the node shuffle with an edge, which admits it (read from that edge's log: no frame shows who dialed whom) |
| groups | no store of any of the five nodes holds a peer of another type (15 stores) |
| roles | the sentinel and the three edges do not serve a call (closed, no reply); the bridge does (`viewer:empty/0`) |

The join checks that need a fresh start (edge1 empty, edge3 holding both) run only the first time after `network.sh start`; later
runs use a weaker form, because the earlier ticks shuffled the views. Result of the last full run: 93 of 93 and 50 of 50, the network
stopped, no process and no port left.

**What these nodes are, and are not.** They are what BEES can build and run today, and no more:

- **Externally driven, with BEES's test unit.** The nodes are built like the bridge and like the nodes of BEES's TEMPUS trials: the
  test unit (`src/tempus_test`) is their clock, fixed at 1500, and no node ticks its stores on a timer. The tokens in
  `lib/tempus_ids.silica` are valid from 1000 to 2000 or 3000, so they are valid at that clock and at no real one. A node that was built
  without the test unit (BEES's production form, `driven: false`) reads the system clock and ticks on timers, but BEES's only token valid
  for a real clock is token 14 (an edge, to 4000000000, made for the clients' trials); there is none for a sentinel or a bridge. Such a
  sentinel or bridge would need new fixture tokens (the producer's key is BEES's test key), and the existing bridge's token 13 would
  have to change too, because it runs on the test clock. This stage does not do that, so **there is no continuous gossip**: the join
  at the start happens by itself; every later shuffle happens when a tick frame arrives (the checks send them). To make an edge a
  long-lived node that gossips on its own, the next step is a `driven: false` build with a minted token; BEES's design allows it.
- **Edges serve no calls.** In BEES's design only the bridge turns an admitted request into a TRUST call. An edge is a client role
  that also listens for shuffles; "an edge answering a call" does not exist, and `run_tempus.py` checks that it is refused.
- **The bridge learns edges through the sentinel only** (its join) and by its own ticks; edges learn the bridge when their bridge
  store ticks.
- **The whitelist rule** (found by trying): a certificate on a node's whitelist must come with a bridge or sentinel token, and an edge's
  certificate must not be listed. So the whitelist of the new nodes holds only certificates 2 (sentinel), 3 (bridge) and 7 (`x4`, the
  checks' bridge-typed client); the three edges use certificates that no whitelist holds. The bridge's list is 2, 3, 4 and 7.
- **Noise in the logs.** Each node's log holds many `root actor exited (no supervisor)` reports and `Silica Actor Failure ... reason
  :normal` blocks: they are the runtime's reports of actors that ended normally (BEES filters them with `tools/bees_tempus_reports.py`).
- **A sample asks for 1 to the store's shuffle length** (3 for the edge store, 2 for the others); a larger number closes the connection
  (`protocol_error`).
- **A sentinel puts every peer that asks it for a sample into its store of that peer's type.** The checks therefore ask it as a
  bridge-typed client (`x4`), so its edge store holds exactly the three edges.
