# Test network

A network built from [BEES](https://github.com/Silica-Language-and-Compiler/project-bees) and the Silica compiler for
the viewer to run against: one bridge, several TRUST nodes and several TEMPUS nodes, serving generated data.
Requirements: `TEMPUS-viewer-requirements.md`, section 14.5. Everything here is TEST data about an invented network, and
the keys and passes are BEES's test-only ones.

Status (2026-11-24): the data and the reference replies exist and are checked. The nodes are not built yet.

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

## Plan for the nodes

Topology (ports are provisional; the bridge's TEMPUS port is the default, 481):

| Node | Kind | Job |
|---|---|---|
| `bridge` | TEMPUS bridge + TRUST client | the viewer's host (`127.0.0.1:481`); routes each published name to a TRUST node |
| `content` | TRUST | `home`, `status`, `directory`, `docs_*`, `gallery`, `image_part` |
| `data` | TRUST | `nodes*`, `node`, `events`, `samples`, `search*`, `live`, `clock`, `slow`, `fail`, `empty` |
| `authority` | TRUST | decides each name's mark (`look_only` or `does_something`) and runs `restart_node` |
| `sentinel`, `edge1`, `edge2`, `edge3` | TEMPUS | a gossip network around the bridge, so the viewer talks to a real network |

Steps, each with a trial and a golden as BEES does:

1. Generate Silica for the replies: one typed vocabulary type (a sum of tagged tuples) and one builder per reply, with
   the large tables built from the same seeded generator in Silica (not literals), and a check that a node's reply bytes
   equal `out/replies/*.etf`.
2. One TRUST node and one bridge answering `home`. A Python or Swift client calls it and compares the reply with the
   reference.
3. Add `content`, `data` and `authority`, the routing in the bridge, and the mark query (requirement 5.11).
4. Add the TEMPUS nodes.
5. A script that starts the whole network and stops it, and a trial that runs the command-line timing test against it.
