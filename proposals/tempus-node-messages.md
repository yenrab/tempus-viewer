# Proposal: messages between TEMPUS nodes

Status: PROPOSAL, revised three times (direct peer to peer only; existing `:etf` encoding and existing transport only; owner rulings of 2026-11-24 folded in). The protocol change belongs in BEES, so this is
written as a proposal to BEES's design (`development-plan/tempus-design.md`) and to the example clients. Date 2026-11-24.

> **Status (2026-11-24).** The owner ruled all 19 open questions (OM-1 to OM-19, section 6) on 2026-11-24. Nothing is built:
> no BEES change, no viewer code, no test-network change, no vectors frozen. Text marked "recommended, ruled" was a
> recommendation that the owner accepted; text marked "overridden" was a recommendation that a ruling replaced. The viewer
> (the Swift application in this repository) sends and receives messages in v1 (OM-9, OM-16 to OM-19); its requirements are in
> `TEMPUS-viewer-requirements.md` section 18 and its work is listed in section 4.5.

Owner constraint received with this task: TEMPUS nodes talk to each other directly, peer to peer, and never through a
bridge or any other node. That removes the relay option (section 2, "Ruled out") and shapes sections 3 and 5.

References are to the BEES clone read for this proposal (commit `ebb3bbf`), written `bees:path:line`. Where I could not find
something I say so. Nothing in BEES was changed.

## 1. Goal and non-goals

Goal. Let an admitted TEMPUS node send an application message to another TEMPUS node it can reach, directly, and let
the receiving application handle it and (optionally) answer. Every example client (Swift, Kotlin, Python, Silica,
gossip drivers), the Silica node and the viewer (the native macOS application of this repository, OM-9) must be able to both send and receive.

Today TEMPUS carries membership traffic only. The requests a node accepts are `shuffle`, `sample`, and (on a bridge)
`call`/`cast` (`bees:src/tempus/bees_tempus_node.part:349-361`: `tn_request`, anything else is refused
`request_refused`, "call and cast are served by a bridge only"). A frame whose `t` is no kind is refused as `protocol_error`
by the connection actor (`bees:src/tempus/dangerous_bees_tempus_conn.silica:711-727`), except on an externally driven
(test) node on loopback, where it goes to the `ext` actor (`bees:development-plan/tempus-design.md:931-995`).
That `ext` hook is a test facility and is not the way to carry messages (section 2, option D).

Non-goals (nothing below changes any of these):

- Membership. Stores, shuffle, sample, join, the three peer types and their isolation stay as they are
  (`bees:development-plan/tempus-design.md:154-228`, 337-360).
- Admission. TLS 1.3, ALPN `tempus/1`, adverts, channel binding, token checks, proof of possession, `key_rotated`
  are unchanged; a message rides on a connection only after the same admission (`bees:src/tempus/dangerous_bees_tempus_conn.silica:6-27`).
- The bridge's `call`/`cast` and TRUST. A message is not a TRUST call and never reaches TRUST. A bridge keeps its
  rule that BEES forwards nothing (`bees:src/tempus/bees_tempus_bridge.silica:9-12`).
- Relaying, store-and-forward, delivery receipts from third parties, a directory, group messaging, ordering across
  messages, end-to-end encryption beyond the TLS hop, large payload transfer, presence.
- Anything but the node-to-node message. The viewer is not excluded: it sends and receives messages in v1 as a node that listens and
  joins gossip as an edge (OM-9, OM-17, OM-19). What a message may do there is limited (OM-16): it is shown to the person and nothing is executed.

## 2. Options

All options are direct node to node. A sender must already know the recipient (section 3.4).

### Ruled out (owner): relay through the bridge or TRUST

Carrying a message through a bridge (an edge `call`s a bridge function that calls onward with `trpc`), or through any
node on the path, is ruled out by the owner. It would also have fought the existing design: a bridge forwards
nothing, and an edge's identity is never passed onward (`bees:development-plan/tempus-design.md:1124-1127`;
"TRUST node to edge, bridge to edge: not provided", line 372). Not considered further.

### Option A: a `message` frame on the existing admitted connection (recommended, ruled: OM-1, OM-3, OM-4)

A new request kind, `message`, sent by the dialing side as the one request of a connection; the answer is one
`message_reply` frame; then close. It reuses TLS, admission, the connection deadline, `inflight_max`, the frame
bound and the refusal behaviour, and it fits the rule "one connection carries one request and its reply"
(`bees:example_tempus_clients/writing-a-tempus-client.md` section 6 and 11).

Costs:
- One full handshake per message (TLS 1.3 with X25519MLKEM768, two adverts, two challenges, two Ed25519 proofs). This is
  the price BEES already pays per shuffle. It is expensive for chatty use; fine for occasional messages. A later
  connection-reuse rule is an open question (OM-4), not part of v1.
- A new kind in the library: `bees_tempus_frame` (kind table, decoder), the connection actor (request and reply
  phases), the node part (dispatch to the application), atoms; plus one new frame in each client language.
- A receiver that is not a bridge keeps no per-peer state ("Nothing is kept per peer outside the views",
  `bees:development-plan/tempus-design.md:407-408`), so per-peer rate limits do not exist there today; section 3.8 adds a
  node-wide bound and leaves per-peer policy to the application.
- It is a protocol change: `tempus/1` gains a kind. An old node refuses a `message` as `protocol_error` (unknown kind, closed
  with no reply). That is a clean failure for the sender, so no `tempus/2` is needed (OM-1).

### Option B (dropped by the owner's ruling): a separate port, ALPN or transport

The owner ruled that node to node communication uses the encoding and the transports BEES already uses, with no new
transport kind. A second port with its own ALPN would be a third TLS profile: the TEMPUS link opens the engine with a
profile number and a fixed ALPN (`open_conn_profile(role, 1, spec)`, ALPN `tempus/1`, TRUST is profile 0;
`bees:src/tempus/dangerous_bees_tempus_tls.silica:3-7`), and I found no configuration that selects another. It would also
not fit the descriptor (four fields, SD-37, `addr` 3 to 261 bytes), so it would change gossip. It is not provided by BEES's
transport selection (section 3.0), so it is dropped. The one thing it offered, isolation of message load from gossip, is
handled by the bounds of section 3.8.

### Option C: messages inside shuffle or sample frames

Piggy-back on gossip. Rejected: a shuffle frame is "one entry that does not verify makes the whole frame refused"
(writing-a-tempus-client.md section 8); mixing payloads into it couples membership correctness to application data, and
gossip partners are chosen at random, not by the application.

### Option D: use the test hook (`ext`, `driven`)

The hook hands unknown kinds to an application actor, but only for `driven` nodes, loopback listeners only, and it
is explicitly "no part of `tempus/1` as the library reads it" (`bees:development-plan/tempus-design.md:931-995`). Production nodes never see
it. Not suitable.

### Recommendation (recommended, ruled)

Option A for v1: a `message` request on the existing admitted `tempus/1` connection, encoded with `encode((:etf), ...)`,
over the existing TLS-over-`(:tcp)` transport, with node-wide bounds (section 3.8) so floods do not starve gossip, and
`ver` in the frame so a later version can add connection reuse. It adds no encoding and no transport.

## 3. Wire definition for the recommended option

Style follows `bees:development-plan/tempus-design.md` section 5 and `bees:src/tempus/bees_tempus_frame.silica`: one ETF
map per frame inside the 4-byte length; key `t` names the message; at most four keys in any map (SD-37); unknown, missing or
repeated keys refused; keys written in name order; one byte form per frame.

### 3.0 Encoding and transport: what exists, and nothing new

Encoding (owner: the same `:etf` as today). Every TEMPUS frame body is the output of the language's `encode((:etf), record)`
over a record whose atoms the program holds, and is read with `decode((:etf), body, { max_bytes, max_depth, max_length })`
inside a `sequence proc[mem(normal), transport]` block (`bees:src/tempus/bees_tempus_frame.silica:1-12`, e.g. `enc_sample` and
`dec_sample` 390-409; the rule for where encode and decode may run is the user ruling in
`bees:development-plan/silica-transport-alignment.md:20, 38-40`, decision D35, `bees:development-plan/roadmap.md` row D35). `(:etf)` is the
first built-in wire format, "the encoding of OTP 26+ `term_to_binary` with no options"
(`bees:development-plan/silica-transport-alignment.md:48`). The frame around the body is the language's `wireframe`: 4-byte
big-endian length. A `message` is therefore a Silica record encoded by `encode((:etf), ...)`; no other encoder is written and the
client languages' own ETF writers (`Etf.kt`, `ETF.swift`, `codec.py`) write the same subset the other frames use.

Transport (owner: the transports BEES already uses). What BEES has, and where it is chosen:

- The carrier is the language's hosted `(:tcp)` carrier, one `carrier_new()` over the stdlib's `dangerous_tcp_carrier`
  (`bees:src/shim/bees_tcp_edge.part:1-11`; decision D35). The language's design also names `(:udp)`, `(:serial)` and `(:ble_gatt)` carriers
  (`bees:development-plan/silica-transport-alignment.md:50`, "design; the hosted ones wait for Silica chunk 9"), but nothing in
  `src/tempus` or `src/trust` uses any carrier except `(:tcp)`; I found no use of the others and did not check which exist in the
  pinned compiler.
- TEMPUS has no transport setting. A TEMPUS connection is always mutual TLS 1.3 over `(:tcp)`, ALPN `tempus/1`, key exchange
  X25519MLKEM768 only, Ed25519 certificates: `bees:src/tempus/dangerous_bees_tempus_tls.silica:1-25`, with the TLS engine OpenSSL on
  hosted platforms (D40). There is no plaintext TEMPUS mode and no classical-key-exchange opt-in
  (same header, "no classical (X25519-only) opt-in ... ruling NQ-8"). The `listen` text and the `spec` credentials are start values
  (`tempus_listen`, `tempus_spec`, `bees:src/tempus/bees_tempus_link.part:20-40`).
- The selection mechanisms that do exist belong to the other modes: BEAM mode picks `transport tcp` or `tls` in `bees.config`
  (`bees:development-plan/bees-config-file.md:169`), TRUST has `plaintext_test_only` (loopback only) and `classical_allowed_certs`
  (D44; lines 208, 232). Neither applies to TEMPUS. Nothing in them is a way to add a message transport.
- Consequence: a message uses exactly the connection a shuffle uses: `tempus_dial` (`bees_tempus_link.part:57-69`) and the accepted
  connection actor, one request, one reply, close. The two boards (ESP32-S3, NUCLEO) use classical X25519 under D41, which TEMPUS
  refuses, so they cannot be TEMPUS nodes and cannot send or receive messages; that is a limit of TEMPUS today, not of this proposal.

Transports each example language speaks today, and what a message needs:

| Language | Speaks today | For messages it needs |
| --- | --- | --- |
| Silica (node, `silica/lib`) | TLS 1.3 over `(:tcp)`, the node's own link and connection actor | nothing new; the node's own units carry it |
| Swift | TLS 1.3 through OpenSSL 4.1+ over a POSIX socket (`Connection.swift`), `tempus/1`, X25519MLKEM768 | nothing new; a frame, a dial wrapper, a listener hook |
| Kotlin | JSSE TLS 1.3 over a `Socket` (JDK 27 for the group; `Client.kt`) | nothing new |
| Python | `ssl` module over a socket, group by library default (guide section 3, 14) | nothing new |
| any | none of them speaks UDP, serial, BLE or plaintext, and BEES's TEMPUS does not either | no new transport; the owner's ruling |

### 3.1 Frame tags and kinds

`bees_tempus_frame@kind_of` today has kinds 1 to 8, 11 to 14 and 0 refused (`bees:src/tempus/bees_tempus_frame.silica:14-18`, 59-72).
Kinds 9 and 10 are free (the removed test frames). Proposal: do not reuse 9 and 10 (their atoms `tick`/`clock` still live in
trials and goldens); take new numbers:

| Kind | `t` atom | Sent by | Meaning |
| --- | --- | --- | --- |
| 15 | `message` | the side that dialed | the one request of the connection |
| 16 | `message_reply` | the side that was dialed | the answer; then close |

New atoms in `bees:src/tempus/bees_tempus.atoms` (D16/D30: every atom must exist at compile time): `message`, `message_reply`, and
key names `to`, `k`, `b`. `ver` and `m` are in `bees:src/trust/bees_trust.atoms:4,6`; `id` is already in the TEMPUS atoms. (I did
not check that every one of these is free of a clash; that is a BEES check.)

### 3.2 `message`

```
#{t => message, ver => 1, to => <<64 bytes>>, m => M}
M = #{id => <<16 bytes>>, k => <<1..32 bytes>>, b => <<0..B bytes>>}
```

Four keys at the top, three in `M`; depth 2 (frame map, `M`). The split into `M` is forced by the four-key limit.

| Field | Meaning | Bound | Enforced |
| --- | --- | --- | --- |
| `ver` | frame version | exactly 1 | after decode (as advert, `bees_tempus_frame.silica` `advert_read`) |
| `to` | the recipient's peer id (SHA-512 of its public key) the sender means | exactly 64 bytes | after decode; the receiver compares with its own id |
| `id` | message id chosen by the sender, random | exactly 16 bytes | after decode |
| `k` | application topic: a byte string, not an atom (atoms are compile-time, D16) | 1 to 32 bytes | after decode |
| `b` | application payload, opaque to BEES | 0 to `msg_max` bytes; literal ceiling 16384 | decode `max_bytes`, then the configured value |
| frame | whole body | at most 16384 + 256 bytes for `message`; the global ceiling 131072 still applies from the length alone | `wireframe@unframe`, then decode |

There is no `from`: the sender is whoever the admission proved (the key of the TLS certificate, bound to the advert's
`pub`, and the token's `sub`). A `from` field would be a claim; the receiver already holds the proof.
The sender's peer id, its descriptor and its token type are handed to the application by the node (the way request 63
carries the peer's descriptor and `m`, `bees:src/tempus/dangerous_bees_tempus_conn.silica:32-34`).

The Silica types, in the form `bees_tempus_frame` uses (fields of a record are written in name order by `encode((:etf), ...)`,
`bees:src/tempus/bees_tempus_frame.silica:3-5`):

```
m: { b: string, id: string, k: string }
message: { m: { b: string, id: string, k: string }, t: atom, to: string, ver: int64 }
message_reply: { b: string, id: string, t: atom, ver: int64 }
decode limits: message { max_bytes: 16640, max_depth: 3, max_length: 16384 }; message_reply { max_bytes: 16640, max_depth: 2, max_length: 16384 }
```

As ETF bytes (the form the clients write, `writing-a-tempus-client.md` section 4): version byte 131; map tag 116 with a 4-byte
arity and the keys in byte order of their names (`m`, `t`, `to`, `ver`; inside `m`: `b`, `id`, `k`); atoms as tag 119
(small UTF-8 atom); a Silica `string` as a binary, tag 109; `ver` as tag 97. Lists are not used. Section 4.3 has complete vectors.

### 3.3 `message_reply`

```
#{t => message_reply, ver => 1, id => <<16 bytes>>, b => <<0..R bytes>>}
```

`id` must equal the request's `id` (else the sender refuses the reply and closes; it counts as a violation by the peer).
`b` is the application's answer, 0 to `reply_max` bytes (ceiling 16384). An empty `b` is a plain acknowledgement. Four keys, depth 1.
The sender's connection reader today accepts only kinds 6, 8, 11 and 14 as a reply (`c_reply`, `bees:src/tempus/dangerous_bees_tempus_conn.silica:694-703`);
it gains kind 16.

### 3.4 Who may send to whom, and how a sender finds a recipient

There is no directory and no name service. A sender can address a node only if it already holds it:

1. From a store: an entry `{ age, d }` has `d = { id, pub, addr, token }`. `addr` is the recipient's listen address. The node
   verifies entries on receipt, so `id`, `pub` and `token` have been checked offline (section 6 of the client guide); but
   entries are hearsay with an age and may be stale or dead (`writing-a-tempus-client.md` section 12).
2. From a connection it has already dialed (it holds the descriptor from the admitted advert).
3. From a connection that was dialed to it: it learns the dialer's descriptor, but the descriptor's `addr` is the dialer's
   advertised listen address, which may not be reachable (NAT; section 3.9). It is usable as an address only if the
   application chooses to trust it.

Procedure for a sender: take the recipient's descriptor `d`; dial `d.addr`; run admission; after the recipient's advert is
checked, require `advert.d.id == d.id` (and `pub`); if not, close without sending the message (the address now belongs to
another node, or the entry was forged). Send `message` with `to = d.id`. The receiver closes with no reply if `to` is not its
own id; this catches a recipient that restarted under a new key at the same address, and a sender that was misled.

The application supplies the descriptor. The library needs one function per language: "send message to this descriptor".
A way to pick a recipient from a store is the application's job (the stores are reachable only through `sample`, as the
Silica peer part says, `bees:example_tempus_clients/silica/lib/bees_tempus_peer.part:30-35`; there is no store read call).
So the application learns recipients from `sample` replies or from `d` of messages it has received (OM-7).

Who may send, by token type (the type is the `typ` of the admitted token, as for every other rule):

| Sender \ Recipient | edge | bridge | sentinel |
| --- | --- | --- | --- |
| edge | allowed if the recipient lists `tempus_edge` in its accepted senders | same | same |
| bridge | same | same | same |
| sentinel | same | same | same |

The library rule is the same for every pair and is a configuration of the receiver, in the style of the bridge's
permission spec ("`none` by default", `bees:development-plan/tempus-design.md:365`): a node is started with a set of
sender types it accepts messages from; the empty set, which a node that does not configure it holds, refuses every
`message`. BEES has no default (OQ-11, OQ-25 pattern). Messages crossing groups (edge to bridge, edge to
sentinel) are allowed by the receiver's configuration (OM-5, ruled); the shuffle isolation of stores is untouched because no store is read or written
by a message.

A bridge needs no special case: a message to a bridge is handled by its application as any other node's. A bridge
receiving a message does not forward it (the owner's rule) and does not run it as a TRUST call.

### 3.5 Delivery semantics

- At most once. A `message` is delivered to the receiving application zero or one time per connection. If the connection
  fails after the sender wrote the frame and before it read the reply, the sender cannot tell whether the receiver handled
  it. The sender may resend with the same `id`; the receiver's application sees both (3.7).
- Direct only. The receiver is the peer at the other end of the admitted connection. No node forwards another node's
  message. No node stores a message for a recipient that is not reachable. If the dial, admission or reply fails, the
  sender is told that it failed, and nothing else (no reason, as BEES says nothing about refusals,
  `writing-a-tempus-client.md` section 7).
- No ordering promise. Each message is its own connection; two messages from one sender may overlap and arrive in either
  order. An application that needs order puts a sequence number in `b`.
- The sender's success means only "the receiver's application answered". It does not mean the application acted.

### 3.6 What the receiver does

After admission the connection actor reads the frame. New dispatch, in the places that exist today:

1. `bees:src/tempus/dangerous_bees_tempus_conn.silica:709-727` (`c_request`): kind 15 joins kinds 7, 12, 13 (`to_node(..., 63)`), so
   the node actor receives it as an admitted peer's request, with the peer's descriptor and type.
2. `bees:src/tempus/bees_tempus_node.part:349-361` (`tn_request`): a new arm for kind 15. The node (a) decodes with `dec_message`
   (exact record, bounds above, `ver` 1), (b) refuses (`request_refused`) if the sender's type is not in its accepted set,
   if `to` is not its own id, or if the node-wide message bound is full, and (c) otherwise casts the application one message,
   in the shape of the bridge's request (op 90 for a bridge is `(:bees, 90, args span, ...)`; a new op number, to be chosen by
   BEES, with s1 the topic and payload, s2 the sender's descriptor, the connection actor as the answer address).
   Only a bridge's op 82/90 path exists today; the node's application currently gets ops 80, 81, 86, 87
   (`bees:src/tempus/bees_tempus_node.part:3-14`), so this is a new application message, not a reuse.
3. The application answers exactly once, as the bridge application does for a call ("answers every request exactly once",
   `bees:src/tempus/bees_tempus_bridge.silica:39`): with a reply payload (becomes `message_reply`), or with "close"
   (the sender sees a failure). The existing answer messages (20 reply body, 21 close, 22 refuse) fit: 20 with an encoded
   `message_reply`, 21 close, 22 refuse (audit line, score at a bridge).
4. The reply is bounded by the connection's one deadline, `shuffle_timeout_ms` (NQ-14). Note the node is "always answers"
   while it works on an admitted request (`...conn.silica:62-63`, phase 16); for messages the application is not the node,
   so the deadline must apply while the application thinks, otherwise a slow application holds a connection. I could not
   verify from the code whether phase 16 has its own timeout; it is stated to wait for the node. A message timer is new
   work in the connection actor (Silica node step 3 in section 6), not a given.

### 3.7 Replay and duplication

- Network replay: a recorded `message` cannot be replayed to the receiver as a new connection, because each connection
  runs a fresh 32-byte nonce in both directions and the proof binds the nonce to the token (`writing-a-tempus-client.md`
  section 6, step 5-6), over TLS. Nothing new is needed.
- Duplicates by the sender (a retry): the `id` lets the application recognise a repeat. BEES keeps no state for it: edges
  keep nothing per peer. Ruled (OM-6): the library does not deduplicate; it hands the application the sender id and the
  message `id` and the application keeps its own window. There is no library ring of recent ids.
- Cross-recipient replay: `to` stops a message addressed to node X being accepted by node Y.

### 3.8 Refusals, score, rate and in-flight bounds

Refusal form is BEES's own: close, no reply body, one audit line locally, nothing said to the peer
(`bees:development-plan/tempus-design.md` section 5, about lines 326-336, "Any violation closes without a reply"). Causes and audit events (names
follow the existing events in the client guide section 7):

| Cause | Audit event | Counted at a bridge (NQ-19) |
| --- | --- | --- |
| frame too long, malformed, unknown or missing or repeated key, `ver` not 1, field out of bound, `to` not this node | `protocol_error` | +1, by the connection actor's refusals (ruling NQ-19, `bees:development-plan/tempus-design.md:1382-1391`; `report` in `...conn.silica:299`) |
| the sender's type not accepted, or no accepted types configured | `request_refused` | +1 at a bridge (a refused request raises the score, `bees_tempus_bridge.silica:18-27`) |
| node-wide message bound full | `inflight_refused` style, a new event `message_busy` | no change (not the peer's doing, as the bridge's total in-flight bound, 17.5) |
| application closed or timed out | `timeout` or `request_refused` | +1 on timeout (a timeout raises the score, 17.5); closed by the application: no change |
| reply with wrong `id` or oversize (seen by the sender) | `protocol_error` on the sender | the sender's own node does not score the node it dialed (no scoring of edges, OQ-12) |

Per ruling NQ-19 the score exists only at a bridge, and "any other node keeps no score and drops it"
(`bees:src/tempus/bees_tempus_node.part:405-417`, `tn_refused_peer`). So on an edge or a sentinel a message flood from one admitted peer is
bounded only by `inflight_max` (global) and the connection deadline. Honest consequence: one peer with a valid token
can keep `inflight_max` connections busy on an edge and starve gossip on that node. Proposed bounds, all literals as
ceilings with configured values at or below them (D47 pattern, no defaults, as OQ-25):

- `msg_inflight`: messages being handled at once on the node, at most `inflight_max`; beyond it, close.
- `msg_rate` and `msg_interval_ms`: node-wide messages accepted per interval (ceiling 1000000 per interval, interval 1 ms to
  3600000 ms, the bridge's own ceilings in 17.5).
- Per peer: at a bridge the existing per-peer table gives rate and in-flight bounds and the score. At an edge or sentinel
  there is none; the application has the peer id in every message and may keep its own table. OM-8 is ruled: no per-peer bound is added to non-bridge nodes (it would be the first per-edge state outside the views). The viewer keeps its own per-sender rate and stored cap (OM-18).
- Sender side: the sender's own dial rate is its application's; the library enforces its connection deadline as for any dial.

### 3.9 Reachability, NAT and firewalls (stated honestly)

A message needs the recipient to be dialable at the address in its descriptor. Each TEMPUS node already advertises a
listen address (OQ-15, "every TEMPUS node is reachable", ruling list at `bees:development-plan/tempus-design.md:119-153`). I found no NAT
traversal, relay, hole punching or STUN in BEES's TEMPUS design or code. So:

- A node behind NAT or a firewall that cannot accept inbound connections cannot receive a message that it did not ask
  for. Gossip already has this limit: nodes that cannot be dialed are dropped as dead partners (section 10).
- A message that a NAT'd node initiates works, and the reply returns on the same connection. So request/reply is the
  one pattern open to a node that can only dial. A message from a reachable node to a NAT'd node fails; the sender sees only a
  failed dial or close, and nothing else.
- Nothing carries the message for the sender: no relay, no store-and-forward (owner's constraint). The application retries
  or gives up. A NAT'd node must have a port open to receive; v1 has no
  long-lived connection, so it cannot receive any other way (OM-4, OM-15: NAT is not handled in v1).
- The viewer listens while the app is open (OM-9, OM-17) and joins gossip as an edge (OM-19). A viewer behind NAT is reachable only where its machine is, as for any node (OM-15).
- The advertised `addr` is the node's claim; a dialer connecting to it learns whether it is right only by admission, which
  checks `id` and the certificate key (section 3.4 step: `advert.d.id == d.id`).

### 3.10 Interaction with the fixed test clock

There is no time field in the message and the library reads no clock for it. What does use time:

- Admission of the sender: the token window is judged by the node's clock, which on an externally driven node is its
  driver's `clock` frames (design section 16.3 and 10, `bees_tempus_node.part:56-60`). A test sets an expiry by sending `clock` to
  the node, so "message refused after the sender's token expired" is testable with the fixed clock exactly as row 12 and 15 of 16.2.
- The connection deadline (`shuffle_timeout_ms`) is on the monotonic clock (`left_ms`, `...conn.silica:57-63`), not the node's
  clock, so it cannot be set by a `clock` frame. A trial that exercises "application too slow" must use a real, short
  `shuffle_timeout_ms`, as the existing timeout rows do (16.2 rows 18, 21).
- Message ids are random. A test must fix them: `id` is an argument of the send function in every client, as the nonce
  already is (`Listener.nonce`, `swift/Listener.swift` struct comments); for the node a fixed draw list exists
  (`draws`, 16.3), but ids are the sender's, so the Silica client takes `id` as an argument.
- The `message` kind is a library kind, so on an externally driven node it is NOT handed to `ext` (the `ext` hook takes only
  kinds that are no kind of `tempus/1`, `ext_request`, `...frame.silica:19`). `tick` and `clock` remain test-only.

## 4. Work needed per component

Line numbers are the current ones in the BEES clone. All paths in 4.1 to 4.4 are relative to the BEES root; section 4.5 is the viewer's work, in this repository. I give the files each
would change from my reading; BEES's author will know of more.

### 4.1 Silica node (`src/tempus`)

1. `src/tempus/bees_tempus.atoms`: add `message`, `message_reply`, `to`, `k`, `b`.
2. `src/tempus/bees_tempus_frame.silica`: `kind_of`/`kind_atom` (59-83) gain 15 and 16; new `enc_message`, `enc_message_reply`,
   `dec_message(body, msg_max)`, `dec_message_reply`, each with its `decode((:etf), ...)` limits (`max_bytes` 16640, `max_depth` 3,
   `max_length` 16384); export them (33-54). Update the header comment that lists kinds (14-18). Records stay at most 4 fields.
3. `src/tempus/dangerous_bees_tempus_conn.silica`: `c_request` (709): add kind 15 to the request kinds; `c_reply` (694): accept kind 16
   on a dialed connection; a deadline for the application's answer while in phase 16 for kind 15 (see 3.6 item 4); the `to`
   check and the check that `advert.id == expected` for a dialed message (new cfg field `expect` or a request-time check; cfg
   already has the whole record so this is a new field in `cfg`, a ripple through `tempus_conn_at` in the link part).
4. `src/tempus/bees_tempus_link.part`: `tempus_dial` (the one dial function, 57-69) already takes `req`, the request body, and closes
   after admission when it is "" , so it can send a message today; it needs the expected peer id parameter.
5. `src/tempus/bees_tempus_node.part`: `tn_request` (349-361) kind 15 arm; the application message (new op) and the new start
   values `{ senders, msg_inflight, msg_rate, msg_interval_ms, msg_max, reply_max }` in `net` or a new record
   (`tempus_node_boot` refuses out-of-range values like the others; update the header comment, lines 1-60).
   `tn_refused_peer` (405-417) is unchanged; a bridge counts message refusals by the same path.
6. `src/tempus/bees_tempus_bridge.silica`: a bridge's table actor `tbr` passes unknown node messages to the application
   (80, 81 are "passed on", header line 21); the new op must be passed on too. No scoring change is needed for the
   NQ-19 events; the per-peer in-flight and rate bounds should apply to messages sent to a bridge (OM-8), which is a change to `tbr`.
7. `tools/bees_tempus_gen.py` (not read in full): the generator that pastes the parts and fills the `$NN$`-style record types;
   it changes if the start record gains fields. I did not read it.
8. `development-plan/tempus-design.md` sections 5, 8, 9, 16.2, `documents/tempus.md` and `example_tempus_clients/writing-a-tempus-client.md`
   sections 4, 7, 8, 9 (new rows, a new request "message", new audit events).

### 4.2 Each example client

All four have one file for frames, one for connection/dial, one for the listener and (not for Silica) one for gossip.

Swift (`example_tempus_clients/swift/lib/TempusClient/`):
- `Frames.swift`: `Frame` enum (line 51) gains `.message` and `.messageReply`; builders `message(to:id:k:b:)`, `messageReply(id:b:)` next
  to `sample`/`done` (178-192); `readBody` (219) reads them with the bounds above; `readAny` (271).
- `Connection.swift`: `dial` (358) must accept a reply of the new kind (the `want:` list in `readFrame`, 274); a
  `sendMessage(to: Descriptor, ...)` wrapper that checks `advert.id == to.id` after admission (`admit`, 299).
- `Listener.swift`: `Request` (line 11) already carries frame, advert and typ; `standardAnswer` (31) answers `message` with `.close`
  today (default branch); add an application handler hook: `messageHandler: (Request, Message) -> Answer`, refusing when
  the sender type is not accepted.
- `Gossip.swift`: the `Peer` (613 lines) holds the listener; gains `send(to:)` and a handler property and the node-wide bounds;
  does not change the store rules.
- `driver/tempus-client/` (the driver) and `test/tempus-client-tests`: a `--send` and `--on-message` option; new tests.

Kotlin (`kotlin/lib/`): `Frames.kt` (195 lines; frames and bounds), `Client.kt` (582; dial, listener, the `Outcome`), `Gossip.kt` (531; the
peer), `Etf.kt` (185; no change expected), `driver/Main.kt`, `test/GossipTest.kt` and `test/Fixtures.kt`.

Python (`python/lib/tempus_client/`): `frames.py` (`read_body` 156, builders 104-148), `connection.py` (`read_any` 311, `Misbehaviour` 331
for the hostile cases, the listener and dial), `gossip.py` (the peer), `testing.py` (fixtures), `__init__.py` exports,
`python/bees_tempus_client.py` (the name trial tools import), `driver/tempus_peer.py`, and the tests
`test_bees_tempus_client.py`, `test_tempus_gossip.py`.

Silica (`silica/lib/`): `bees_tempus_client.silica` (pure frame builders and readers over `bees_tempus_frame`),
`bees_tempus_client.part` (active part; `tempus_client_dial`, `tempus_client_answer`; add `tempus_client_send_message` and
a listening answer for kind 15), `bees_tempus_peer.part` (the peer: starts the node, which handles the receive path;
only the application message and start values pass through), `driver/peer.role` and the `g*.role` and `gs.role` scenarios,
`driver/Makefile`.

Gossip runner: `example_tempus_clients/gossip/gossip_run.py` and its `Makefile` (new `messages` check; section 4.4).

Each client's README (`*/README.md`) and `example_tempus_clients/README.md` need a line.

### 4.3 Conformance vectors (ETF bytes, shared by all languages)

The existing conformance is: each client builds and reads the same frames and the trials compare bytes
(`writing-a-tempus-client.md` section 4: the form "the trials compare byte for byte"); the Python rules are compared with the
models `tools/bees_tempus_view_model.py` and `tools/bees_tempus_store_model.py` (design 16.7). I found no single shared vector
file for the TEMPUS clients (`contract/conformance` is for the BEAM-mode wire). Proposal: one file,
`example_tempus_clients/conformance/message_frames.txt`, one vector per line (name, expected verdict, hex of the ETF body),
read by all four test suites and by the Silica node's trial.

The bytes below are the ETF bodies of the frames of section 3, in the form the clients write (3.2). I produced them with the
Python example's own writer (`python/lib/tempus_client/codec.py`, `etf_encode`) and read none of them with the Silica
`encode`; BEES must regenerate them with `encode((:etf), ...)` on the node side and freeze them only if the bytes are equal
(the agreement of two independent writers is the evidence, design 16.5). `to` is 64 bytes `aa`, `id` is 16 bytes `01`.

| Vector | Expected | Bytes | ETF body (hex, without the 4-byte length) |
| --- | --- | --- | --- |
| V1  message, k=ping, b empty | valid | 151 | `83740000000477016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b6d0000000470696e6777017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77037665726101` |
| V2  message, b=hi | valid | 153 | `83740000000477016d74000000037701626d000000026869770269646d000000100101010101010101010101010101010177016b6d0000000470696e6777017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77037665726101` |
| V3  message_reply, b empty | valid | 64 | `8374000000047701626d00000000770269646d0000001001010101010101010101010101010101770174770d6d6573736167655f7265706c7977037665726101` |
| V4  message_reply, b=ok | valid | 66 | `8374000000047701626d000000026f6b770269646d0000001001010101010101010101010101010101770174770d6d6573736167655f7265706c7977037665726101` |
| I1  ver 2 | refused | 151 | `83740000000477016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b6d0000000470696e6777017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77037665726102` |
| I2  unknown key x | refused | 156 | `83740000000577016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b6d0000000470696e6777017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa770376657261017701786101` |
| I3  k empty | refused | 147 | `83740000000477016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b6d0000000077017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77037665726101` |
| I4  to 63 bytes | refused | 150 | `83740000000477016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b6d0000000470696e6777017477076d6573736167657702746f6d0000003faaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77037665726101` |
| I5  id 15 bytes | refused | 150 | `83740000000477016d74000000037701626d00000000770269646d0000000f01010101010101010101010101010177016b6d0000000470696e6777017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77037665726101` |
| I6  k an atom, not a binary | refused | 148 | `83740000000477016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b770470696e6777017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77037665726101` |
| I7  one byte after the term | refused | 152 | `83740000000477016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b6d0000000470696e6777017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa7703766572610100` |
| I8  keys out of name order | refused only if OM-2 rules key order checked | 151 | `8374000000047703766572610177017477076d6573736167657702746f6d00000040aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa77016d74000000037701626d00000000770269646d000000100101010101010101010101010101010177016b6d0000000470696e67` |

Built by rule instead of listed (their bytes are too long to be useful here; same construction as V1 with the field changed):

- V5 maximal: `k` 32 bytes, `b` 16384 bytes; V6 `message_reply` with `b` 16384 bytes. Valid.
- V7 `b` holds all 256 byte values. Valid.
- I9 `k` 33 bytes; I10 `b` 16385 bytes; I11 the whole body one byte over 16640. Refused (field and frame bounds).
- I12 `M` written as a list instead of a map; I13 a `message_reply` whose `id` differs from the request's (checked by the sender
  only); I14 nesting one level deeper than 3; I15 a repeated key (two `ver`). Refused.
- Receiver-side, not decidable from bytes alone: I16 `to` is another node's id; I17 the sender's type is not accepted;
  I18 a `message` frame sent before the adverts. Each is closed with no reply and one audit line.

Expected observation for every refused vector: a listening client closes with no reply and counts a refusal; the dialing
client sees a closed connection and nothing else (no reason is ever sent, `writing-a-tempus-client.md` section 7).
The Python reader accepts keys in any order (I decoded vector I8 with it), so whether I8 is refused is a ruling (OM-2),
not an existing behaviour.

### 4.4 Cross-language matrix trial

Model on `trials/c7_tempus_gossip` (a leaf Makefile delegating to `example_tempus_clients/gossip`; the runner
`gossip_run.py`; `mixed` and `trio` networks; goldens `NAME.check` per platform) and on `trials/c2_tempus_clients/COVERAGE.md`
(row-to-step coverage table).

- New trial `trials/c8_tempus_messages` (the next free c-number; `c7` is the last I saw). Leaf `Makefile`, `platforms`,
  ports from `tools/trial_ports.py` like c7.
- Network: the `mixed` network (Silica sentinel and one edge each of Silica, Python, Kotlin, Swift), plus a check phase after
  gossip converges: every one of the four edges sends one message to every other edge (12 pairs), using the descriptor it
  learned by `sample`/gossip, each with a fixed `id`; each receiver's handler answers with `b` = SHA-512 of the payload; the
  runner asserts the sender got the expected reply. Output is a matrix `sender x receiver` of ok/fail, recorded as a
  golden check like the existing ones.
- Negative cases in the same run, per language pair: a message to a node that is down (fail); a message with `to` of another
  node (fail, receiver audit line); a sender type that the receiver does not accept (fail); an oversize payload (fail); a
  token expired by `clock` on an externally driven receiver (fail).
- Conformance vectors (4.3) run first in each language's own unit tests, so a wire error is found before the matrix.
- Only one network at a time on the c7 ports; the matrix runs after c7, not beside it.

### 4.5 The viewer (Swift application, this repository)

Ruled in OM-9 and OM-16 to OM-19. The viewer uses the Swift TEMPUS client library in `project-bees` in place (it is not copied), so
the library work of 4.2 (Swift) is a prerequisite. The viewer's own work, in files of this repository that are to be created (no
file named here exists yet; names are indicative, and the viewer's requirements are `TEMPUS-viewer-requirements.md` section 18):

1. A listener in the Swift host: it binds a fixed, configurable port while the app is open and closes it when the app quits
   (OM-17). It runs the library's listener with a message handler (the hook of 4.2) and the receiver's accepted-sender set (empty
   by default, OM-5, chosen by the person per network, OM-18). It refuses everything while receiving is off for the network.
2. Gossip membership as an edge (OM-19): join through a sentinel, the shuffle timers and the three stores kept by the library's
   `Peer`, an advertised `host:port` (editable; default the machine's LAN address and the configured fixed port), and the
   edge token that the network owner issues for the viewer's key, held beside the bridge pass. The same Keychain seed serves both roles.
3. Sending: a compose form (recipient key and address, topic, body up to 16384 bytes) that calls the library's send-message wrapper,
   checks the recipient's id after admission (3.4), and shows the reply or "not delivered".
4. A messages view and its state in the host's store: newest first (network, sender key fingerprint, topic, time, preview, full
   body as text), a badge and a tab-bar count, no system notifications, block by key, per-sender rate (default 10 a minute),
   stored cap (default 1000, oldest dropped), kept only while the app is open (OM-18). A message is only displayed; no command is
   executed from it (OM-16).
5. Settings per network: receiving on or off (off by default), accepted sender types, the port, the advertised address.
6. Checks: the conformance vectors of 4.3 against the library's reader the viewer uses; golden trials of the pure parts (accept
   rules, block list, rate and cap); a written checklist for the window parts, as for the rest of the viewer.

## 5. Test-network use

The test network `testnet/README.md` stage 3 has `sentinel` (24430), `edge1` to `edge3` (24431 to 24433), `bridge` (24401);
the edges are built from `nodes/tempus` with one role file each. Do not run this against the ports while trials
are running there.

- Stage 3 edges and sentinel become senders and receivers: the node `node.role` gets the message start values and a handler
  that answers with a digest (the same as the c8 trial). `network.sh` is unchanged.
- Checks to add to `testnet/run_all.sh`'s 50 TEMPUS checks: edge1 sends to edge2 and edge3 (descriptors obtained by
  `sample` from the sentinel, as the existing checks already do); the sentinel sends to an edge (cross token type; allowed by OM-5 when the edge's accepted set holds `tempus_sentinel`); an edge sends to the bridge (the bridge application refuses by configuration unless its accepted set holds the sender's type, OM-5); a message to a stopped edge fails; a message to an unreachable address fails with no relay (nothing else in
  the network learns of it, observed in the other nodes' output).
- Stage 1 and 2 (the bridge and TRUST nodes) are not involved by messages. The viewer's existing checks (bridge calls) are not changed.
- The viewer as a node (OM-9, OM-19): the viewer's key needs an edge token as well as its bridge pass, made by the test-only tool the
  same way (the viewer's requirements, 4.9 and section 18), and the viewer must be admitted by the sentinel and shuffle into the edge
  store so that an edge can learn its address by `sample`.
- A node that messages the viewer: one stage 3 edge sends a message to the running viewer (descriptor from `sample`), with receiving
  switched on and `tempus_edge` accepted in the viewer, and a check that the viewer shows it (by hand, from the viewer's window
  checklist; the viewer's golden trials cover the accept rules). A refused case: the same message with receiving off or the sender
  blocked, which the sending edge sees only as a closed connection.
- The viewer sending to an edge: the viewer's compose form to an edge whose accepted set contains the viewer's token type; the edge's
  digest handler answers and the viewer shows the reply. Also a send to a stopped edge, shown as "not delivered".
- The loopback test network does not test NAT or the macOS incoming-connection prompt (OM-15, OM-17).
- A positive "no relay" check: the bridge's output shows no message lines for a message between two edges.

## 6. Open questions for the owner

Each has options and a recommendation.

- OM-1. **RULED 2026-11-24 by the owner: new kinds inside `tempus/1` (the recommendation).** Where does the change live: new kinds in `tempus/1` (recommended) or `tempus/2`? A `tempus/2` ALPN (a new ALPN name, so against the no-new-transport ruling unless the owner allows it) would let old
  nodes refuse at the handshake, but forks every client. Recommendation: kinds in `tempus/1`; an old node refuses an
  unknown kind with a plain close, which the sender treats as failure.
- OM-2. **RULED 2026-11-24 by the owner: kinds 15 (`message`) and 16 (`message_reply`); the short key names `to`, `k`, `b`; keys in name order REQUIRED (a frame with keys out of order is refused, so vector I8 is invalid).** Key names, kind numbers, and whether key order is checked. The guide (section 14) says it did not check whether a node
  accepts other valid ETF forms. Options: (a) the letters above; (b) longer names (`topic`, `payload`). Recommendation: (a) is
  compact but BEES's atoms are few; (b) reads better and costs a few bytes. Owner (or BEES) to choose; order: require it, as the
  other frames do ("keys in name order", section 5).
- OM-3. **RULED 2026-11-24 by the owner: messages ride the existing TLS 1.3 over `(:tcp)` `tempus/1` connection only; the ESP32-S3 and NUCLEO boards stay outside TEMPUS. Other carriers (`:udp`, `:serial`, `:ble_gatt`) are not part of this proposal.** Transport. Ruled by the owner: no new transport and no new encoding. What remains to confirm: messages ride
  the existing TLS-over-`(:tcp)` `tempus/1` connection only (section 3.0), so the two boards (classical X25519, D41) stay
  outside TEMPUS and cannot message. Recommendation: confirm; revisit only with a TEMPUS ruling for boards (NQ-8 is the
  current ruling that TEMPUS is hybrid-only).
- OM-4. **RULED 2026-11-24 by the owner: (a) one message per connection for v1. Connection reuse (b) and a persistent channel (c) are not part of v1; (c) is to be ruled on separately.** One message per connection, or allow several on one connection (and later a long-lived channel for NAT'd nodes).
  Options: (a) one per connection as for every request today; (b) up to N messages per connection; (c) a persistent channel.
  Recommendation: (a) for v1; (c) is the only way a NAT'd node could receive and would be a new design (liveness, idle
  timers, flow control) that the owner should rule on separately.
- OM-5. **RULED 2026-11-24 by the owner: (a) any admitted peer may send to any type; the receiver decides by a configured set of accepted sender types, empty by default (a node refuses every message until configured).** Does a message cross token types (edge to bridge, edge to sentinel, bridge to sentinel)? Options: (a) any admitted
  peer to any type, receiver's config decides; (b) same type only (edge to edge, bridge to bridge, sentinel to sentinel);
  (c) edge to edge only. Recommendation: (a) with the receiver's accepted-sender set empty by default, so nothing is
  accepted until configured. Reason: BEES already limits who may do what by type ("TRUST decides what a member may do",
  `documents/semp.md` as quoted in design section 7), and a bridge or sentinel that accepts messages from edges takes on
  edge-controlled load that today it takes only for `sample`/`call`.
- OM-6. **RULED 2026-11-24 by the owner: application only; the library keeps no ring of recent ids.** Duplicate suppression: application only (recommended) or a bounded library ring of recent `(peer id, id)` per node.
  The ring is state per peer, against the "no per-edge state" rule (design section 8).
- OM-7. **RULED 2026-11-24 by the owner: (a) only through `sample` replies and the descriptors of messages received; no store-reading library call in v1.** How an application finds recipients. Options: (a) only through `sample` replies and the descriptors of messages
  received (nothing new); (b) a library call to read a store (today there is none: stores are reached over `tempus/1`
  only, `bees_tempus_peer.part:30-35`). Recommendation: (a) for v1.
- OM-8. **RULED 2026-11-24 by the owner: (a) node-wide bounds only; per-sender limits are the application's, or a bridge's own table.** Per-peer rate and in-flight bounds on non-bridge nodes. Options: (a) none, node-wide bound only (v1); (b) a per-peer
  table at every node, as a bridge has. (b) breaks "no state per edge" and makes a table that an attacker with many valid
  tokens can fill (the answer in design 17.5 is the same: the limit is the producer's issuance). Recommendation: (a), the
  application keeps its own table; (b) only on nodes that choose to be bridges.
- OM-9. **RULED 2026-11-24 by the owner: the viewer both sends and receives messages in v1. This overrides the recommendation below, whose premise (the viewer holds no identity) was wrong: it holds a key and a pass. Consequences (the viewer must listen, be reachable, what a received message does, what the person sees and approves) are open: see OM-16 to OM-19.** Does the viewer send or receive messages? (The question as asked: it was then taken to be a client of the bridge only that cannot listen.) Recommendation, overridden by the ruling above:
  no, not in v1: no inbound, and no outbound either, because the viewer holds no token and no TEMPUS identity in the
  current design (not verified against `TEMPUS-viewer-design.md`; check before ruling). If wanted later: outbound-only
  request/reply to a node that accepts the viewer's type.
- OM-10. Spoofing. **RULED 2026-11-24 by the owner: (a) the connection and admission suffice; no per-message signature.** A message cannot be spoofed past admission: the sender is the key of the TLS certificate bound to the
  token and proved by the nonce signature (client guide section 6). The remaining risks are application-level (a
  peer with a valid token says what it likes, an `edge` token being cheap to obtain per 17.5). Options: add a per-message
  signature by the sender's key (non-repudiation, forwarding by others, though forwarding is ruled out); recommendation:
  no, the TLS channel and admission suffice for a direct message.
- OM-11. Amplification. **RULED 2026-11-24 by the owner: (a) accept; reply ceiling equals message ceiling (16384).** A reply can be larger than the request (up to 16384 bytes of `b` for a 1-byte request) but there are no
  third parties to reflect to (direct, no `from`), and a TCP/TLS handshake must complete first, so source-address
  spoofing does not apply. Option: cap `reply_max` below `msg_max` (recommend equal, 16384). Recommendation: accept.
- OM-12. Flooding. **RULED 2026-11-24 by the owner: (a) node-wide bounds are enough for v1; measure with a hostile sender in the matrix trial. The viewer also needs its own per-sender rate and stored-message cap (see OM-18).** See 3.8: node-wide bounds, plus the application's own per-peer table. Question: are node-wide bounds
  enough for an edge? Recommendation: yes for v1, measure in the matrix trial with a hostile sender.
- OM-13. **RULED 2026-11-24 by the owner: 16384 bytes (message `b` and reply `b`).** Payload size ceiling: 16384 (recommended; below the 131072 frame ceiling so message memory at `inflight_max` 64 is
  64 x 16 KiB = 1 MiB, comparable to the stores' 1.2 MiB in design section 8). Alternatives: 4096, 65536.
- OM-14. Topic `k`: **RULED 2026-11-24 by the owner: an opaque byte string (1 to 32 bytes); no registry of atoms.** an opaque byte string (recommended) or a registered atom set. Atoms need compile-time presence (D16), so
  a registry would make every program list every topic.
- OM-15. NAT (see 3.9): **RULED 2026-11-24 by the owner: NAT is not dealt with in v1. No hole punching, no relay; section 3.9 stays as the statement of the limit.** is outbound-only enough for the viewer's use, or does the owner want hole punching or a relay
  node? A relay is ruled out; hole punching is out of BEES's scope and I found no design for it.

- OM-16. **RULED 2026-11-24 by the owner: a message received by the viewer is shown to the person** (a notice or an item in a messages view, with the sender's key and the topic). Nothing runs and no command is executed from a message. The accepted sender types are chosen by the person per network (empty by default, OM-5).
- OM-17. **RULED 2026-11-24 by the owner: the viewer listens on a fixed port while the app is open** and receives nothing when it is closed. It is reachable only where its machine is reachable, and macOS asks the person to allow incoming connections.
- OM-18. **RULED 2026-11-24 by the owner: accept the recommendation.** Messages view (newest first: network, sender key fingerprint, topic, time, preview; full body as text), badge and tab-bar count with no system notifications; receiving OFF by default and set per network; accepted sender types chosen per network (default none); block a sender by key; configurable per-sender rate (default 10 a minute) and stored cap (default 1000, oldest dropped); a compose form (recipient key and address, topic, body up to 16384 bytes) showing the reply or "not delivered"; messages kept only while the app is open. What the person sees and controls: the messages view, notices, per-network on/off for receiving, accepted sender types, blocking a sender, size of the stored history.
- OM-19. **RULED 2026-11-24 by the owner: (a) the viewer joins gossip like an edge**: it asks a sentinel, is inserted into the edge store, and other nodes learn its address by shuffling. Consequences to carry into the requirements: the network owner issues the viewer an edge token for its key; the viewer runs the join and the shuffle timers and keeps the three stores; the viewer advertises a reachable `host:port` (editable, default the machine's LAN address and a configurable fixed port); the viewer's pass for a bridge and its edge token are both held. How a node learns the viewer's address and token: the viewer needs an advertised `host:port` and a token usable as a listener (requirements section 14 notes that `dial` requires an advertised `host:port`), and a way to join the node's stores or be handed out, so that other nodes can find it. This affects the requirements (the viewer is a listening node, not only a requester of a bridge) and the test network.

## 7. Risks and implementation plan

Risks:
1. Starvation of gossip on a node by message traffic, since only `inflight_max` bounds a non-bridge node. Mitigation: node-wide
   bounds from the first step; measure in the c8 trial.
2. The application-answer timeout in the connection actor (3.6 item 4) is new behaviour in the one actor all admission
   goes through; a mistake would affect membership. Mitigation: keep it to the message kind; existing goldens must stay
   byte-identical.
3. Silica's four-field record limit (SD-37) and the pinned compiler's copy cost (W2300) may force shapes (the `M` split is
   one such). A message record with a 16 KiB `b` copied per dispatch is within the stated 8 MiB budget for 64
   connections only if copied a few times; not measured. Measure the ceiling (ruled 16384, OM-13) in the c8 trial.
4. Four implementations of one new frame: a divergence is likely without shared vectors; hence the ETF vector file first. Python's reader accepts keys in any order, so a strictness decision (OM-2) must be made before the vectors are frozen.
5. NAT: users may expect delivery to every node; it will fail to some (3.9). The docs must say so.
6. A change to the connection actor's `cfg` record ripples through the link part and generator (4.1 item 3, 7) and
   through every trial leaf that builds a node.
7. Old goldens: any trial golden listing the frame kinds or the audit lines of an unknown kind is unaffected (the new
   kinds are opt-in by configuration), but the guide and design text change.
8. The viewer listens (OM-17): a person's machine accepts incoming connections from the network while the app is open. Mitigations ruled:
   receiving off by default, accepted sender types empty by default, block by key, a per-sender rate and a stored cap, nothing
   executed from a message (OM-16, OM-18). Still a risk: a valid peer can fill the person's messages view up to the cap, and the
   macOS firewall prompt and entitlements for a listener are untested (viewer requirements OI-21).
9. The viewer as an edge needs an edge token from the network owner and real-clock token handling that BEES does not have for
   sentinel or bridge (only the fixed test clock). Without them the viewer can join only a test network. (Viewer requirements OI-20, OI-22.)
10. The viewer's advertised `host:port` is its own claim and may be wrong or unreachable (NAT, a changed LAN address): senders see only a failure (3.9).
11. I could not run anything (the network is in use by another agent) so all claims are from reading.

Ordered plan with rough sizes (S under a day, M a few days, L about a week; one engineer familiar with BEES):

| Step | Work | Size |
| --- | --- | --- |
| 1 | Owner rulings on OM-1 to OM-19 (done 2026-11-24); BEES design text: sections 5, 8, 16.2 rows, a new section on messages | S |
| 2 | ETF vector file (4.3) regenerated with the Silica `encode((:etf), ...)` and compared with the Python writer's bytes; Python reference reader/builder first (fastest) | S |
| 3 | Silica node: atoms, frame unit, `conn` kinds 15/16, `tn_request` arm, application op, start values, bounds, the answer timeout; trial leaf `t`-series for the node alone (a scripted Python sender) | L |
| 4 | Python client: frames, dial, listener handler, tests, driver option | S |
| 5 | Kotlin client | M |
| 6 | Swift client | M |
| 7 | Silica client and peer part; `tools/bees_tempus_gen.py` if needed | M |
| 8 | c8 matrix trial and goldens on the three platforms (Mac, Linux x86-64, Linux AArch64, as BEES records) | M |
| 9 | Test network: handler in `node.role`, new checks in `run_all.sh`; docs (READMEs, writing-a-tempus-client.md) | S |
| 10 | Viewer (this repository, after step 6 gives the Swift library its message frame and listener hook): listener, gossip as an edge, messages view, compose form, settings (4.5); edge token for the viewer's key in the test network (5) | L |

Step 10 depends on step 6 and on the viewer's own build; it does not change BEES. Step 3 is the critical path and the only one that can break existing membership behaviour; steps 4 to 7 can run in parallel
after step 2. Total about three to four weeks of one person, less in parallel. These are estimates from line counts of the files named
(the Swift `Frames.swift` is 280 lines, `Listener.swift` 243, the Silica `conn` unit 849), not from measurement.
