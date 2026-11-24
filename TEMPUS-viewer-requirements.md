# TEMPUS viewer: requirements

Status: first draft, written 2026-11-23 from an interview with the owner. It follows
`TEMPUS-viewer-design.md` (the design notes, which hold the options considered and the BQ numbers cited here). Every
requirement below was either ruled by the owner in the interview or is a stated consequence of a ruling. Where the
owner has not ruled, the item is in section 15 and is not a requirement.

Revision 2026-11-24: after reading `project-bees` and `silica` the owner ruled on the points in section 15 (OI-3
partly, OI-6, the network client, call arguments, the test network, passes, domain names, the compiler). Those
rulings are folded into sections 2, 3, 4, 5, 14, 15 and 16.

Revision 2026-11-24 (messages): the owner ruled OM-1 to OM-19 of `proposals/tempus-node-messages.md`. The viewer sends and
receives node-to-node messages in version 1, so it is no longer only a client of a bridge: it listens while the app is
open and joins gossip as an edge. The change is in sections 1.5, 2.7, 2.8, 4, 11, 13.1, 14, 16, 17 and the new section 18,
and in open items OI-12 and OI-20 to OI-25.

Wording: "must" is a requirement. "Should" is a strong preference that may be dropped with a reason. "The viewer" is
the new native application, not a web browser.

## 1. Purpose and scope

1. The TEMPUS viewer is a native macOS application, written in Silica, that a person uses to visit places on TEMPUS
   networks. It does not use HTTP or HTTPS.
2. It sends a request to a bridge. The reply is a list of commands. The viewer carries the commands out as native
   macOS controls.
3. It is a general tool. No first application is chosen. Test applications are written as needed.
4. Version 1 is for public networks, with admission as in section 4.
5. Version 1 runs on macOS only.
6. The viewer is also a TEMPUS node for messages (ruled 2026-11-24, OM-9 of the messages proposal): it sends a message
   to another node and receives messages from other nodes, directly, peer to peer. Section 18 holds the requirements.

### 1.1 Rulings carried over from the design document

- R1. The unit is a command, not a page.
- R2. One render may be built from more than one request. The frame size therefore does not limit a render.
- R3. No reply holds code. A command is data that selects a behaviour the viewer already has. No command carries a
  condition, loop, expression, template with logic or reference to code to load.

## 2. Architecture

1. The viewer is a Silica application designed to Silica principles: a root supervisor, a supervision tree of
   whatever depth suits, many actors each with one responsibility, and `cast` in preference to `call` wherever
   possible.
2. Windowing and drawing use SwiftUI (ruled 2026-11-24), not the older imperative, object-oriented approach of
   building and mutating views. Silica does not call SwiftUI directly. A Swift host
   exposes a C interface, and Silica reaches it by FFI through guarded worker actors (the pattern in
   `silica/trials/ffi_addition`).
3. The Swift host is a SwiftUI application. It owns the main thread and the run loop that SwiftUI starts. Its views
   are a function of state: a store of observable state holds the current display (tabs, regions, content). Silica
   casts commands to the host, the host changes that state on the main thread, and the views redraw from it. No
   code builds or edits a view directly. Where SwiftUI lacks a needed control, the host may wrap one native control
   inside SwiftUI, and each such wrapper must be listed in this document with its reason.
4. Events (clicks, keystrokes, window changes) travel from the Swift host into Silica without any call into the Silica
   runtime. The host pushes each event onto a queue in its C layer. A Silica FFI worker blocks in a C function that
   takes the next event from that queue, casts it to a supervised listener actor, and asks itself again. The host
   never waits for a reply. A failed listener must be restarted by its supervisor. (Shown by the OI-13 spike.)
5. Drawing travels the other way. A window actor casts a command to an FFI worker, which passes it to the host.
6. Network work must never freeze a window.
7. Networking, TLS 1.3 with X25519MLKEM768, Ed25519 and admission are provided by the Swift TEMPUS client library
   in `project-bees/example_tempus_clients/swift` (`TempusClient`), used as it is. It must not be copied into this
   project. It is a dependency, built from its own place. Bugs found in it are fixed there, in the BEES project.
   For bridge requests the viewer is an admitted edge and needs no new kind of token and no change to admission. For
   messages it is also a listening node (section 18): it holds an edge token in addition to its bridge pass, and the
   library's listener and gossip peer are used in the app. The viewer is not a client only.
   Silica actors drive it through the Swift host and the FFI workers of requirement 2.2: a request actor casts a
   request to an FFI worker, which calls the library and casts the outcome back.
8. The viewer must be built from separate responsibilities at least along these lines (names are indicative):
   network store, key store, address parsing, request sending, reply checking, render assembly, tab, history, kept
   copies, window, event listening, refresh timers, and for messages (section 18): listener, gossip membership, message
   sending, message store, block list.
9. Toolchain (ruled 2026-11-24, replacing the earlier "latest link" wording): the viewer, the bridge, the TRUST nodes
   and the TEMPUS nodes of the test network are built with the compiler binaries published in the releases of the
   public Silica repository (https://github.com/Silica-Language-and-Compiler/silica/releases), not with a compiler from
   a local checkout. The latest release is the one to use unless a ruling says otherwise, and no version is pinned
   in this project. The release compiler does not carry the standard library units (`wire_etf`, `Supervisor`,
   `Carrier` and others), so a build also takes their sources from the public Silica repository at the commit named
   in the release's tag (the tag `compiler-<commit>`), never from an arbitrary local branch. (Ruled 2026-11-24, OI-18.
   The three units the two spikes borrowed were checked against the commit of release `e53689e` and are identical.)
   The Swift host builds with the installed Swift and the installed OpenSSL (4.1.0 or later, as
   BEES's `contract/what-is-required-to-use.md` requires).

## 3. Addresses and links

1. The only link scheme the viewer accepts is `tempus://`. Every other scheme must be refused, wherever it appears:
   in the address entry, in a command, in a pasted link, and in a request from the operating system.
2. The form is `tempus://host[:port]/name?arguments`.
3. The host is a domain name or an IP address, and both must work. It identifies one specific bridge. The viewer
   connects to that host and port, resolving a domain name in the Swift host (the library uses `getaddrinfo`). There
   is no discovery of other bridges in version 1.
4. `name` is a name that the network owner published. The application maps it to a function. Raw module and
   function names must not be accepted in an address.
5. Arguments are byte strings (text) only (ruled 2026-11-24, OI-17). A whole number or true/false is written as text, so an address can be copied, sent and
   bookmarked.
6. An address names only the first request of a render. Later requests come from commands and need no text form.
7. The default port is 481, used when an address names none. It is a configuration value (section 11), not a constant.

## 4. Networks, keys and passes

1. The viewer may contact a host only for a network the person has added. A link to a host that belongs to no
   added network must produce a clear message that the network has not been added, and no connection is made.
2. Adding a network is a step in the viewer, and the person does it by importing a file. The file is in the
   Erlang external term format (ETF), as BEES encodes everything. It never holds a private key. It holds the network's
   producer key, a label, one or more bridge hosts with ports, and the pass. The person supplies what the network owner publishes outside the
   network (the producer's key, a label, and the host or hosts). The person gives the network a name.
3. The viewer holds one Ed25519 key per network. Keys are made by the viewer. The same key serves both roles: the
   bridge pass and the edge token of section 18 are both issued for it.
4. Admission is by a per-person pass. The viewer shows the public half of the key for that network so the person
   can send it to the network owner. The owner returns a pass signed for that key. The person imports it.
   The owner also issues an edge token for the same key if the person is to join gossip and receive messages (section 18.3).
   For now, passes are test-only: a test tool signs a pass for the viewer's own key with BEES's fixed test producer seed
   (requirement 4.9). No tool for issuing real passes is built in this phase, and the test passes must never be
   treated as real ones.
5. The pass lifetime is judged by the bridge on its own clock. The viewer must record each pass's expiry, warn the
   person before it expires, and say plainly when it has expired and offer the import step again.
6. Automatic renewal of a pass, a guest tier, and an open token endpoint are not in version 1. Networks that want
   public access publish the means of getting a pass outside the network.
7. Private keys must be stored in the macOS Keychain. One seed per network serves the key for requests and the key for
   messages and gossip; no second key is made.
8. State is separate for each network, with no exception.
9. Test passes (ruled 2026-11-24, replacing the earlier "fixed test key" mode). The viewer always uses the key it made
   and keeps in the Keychain, in test builds too. A pass for that key is made by a separate test-only tool, which
   signs it with BEES's fixed test producer seed, using the Swift client library's public calls (`tokenPayload` and
   `SigningKey.sign`). The same tool signs the edge token for the viewer's key (section 18.3). The viewer therefore holds no test key and no test switch. The tool must live outside the
   viewer's build, and a production build of the viewer must not contain it or the test producer seed. A check (as in
   BEES's `production-check`) must show that.

## 5. Requests

1. A request is made with `call` through a bridge, using the existing BEES protocol.
2. Every published name carries one of two marks: look-only or does-something. The mark is sent by the bridge. The
   decision is made in a TRUST node behind the bridge, not in the bridge. The bridge never decides it. (How and when
   the mark reaches the viewer relative to a request is open: OI-3.)
3. A link from outside the viewer (pasted, from another application) may open only a look-only name. A
   does-something name must refuse to run from an outside link, and runs only when the person acts inside the
   viewer, for example by pressing a button.
4. Only look-only requests may be sent automatically, refreshed on a timer, or kept for reuse.
5. A command may name requests only on its own network.
6. A form sends its fields as one flat list of byte strings: each field's name, then its value, in the order of the
   form (a tick box is `true` or `false` as text, a number is its digits). The function must treat them as
   untrusted input.
7. A refusal, a failed function and a timeout look the same to the client. The viewer must show one message,
   "could not be fetched", in the region that was waiting. A function that ran and wants to report a problem does so
   by returning display commands.
8. Whether connection reuse is needed is decided after the trial in section 14. Until then the viewer must work
   with one request per connection.
9. The viewer must slow down by itself when it is refused, and must not exceed the limits in section 11.
10. Request arguments are one list of byte strings (ruled 2026-11-24, OI-17), which is what a TRUST export's single
    element type allows (`args string`). The Swift `callFrame` takes whole numbers only (`args: [Int64]`) and must be
    updated, in `project-bees`, to carry byte strings. The Silica client's frame builder and the bridge's reading of
    arguments must be checked to agree, with the BEES conformance goldens extended to cover them.
11. Mark query (ruled 2026-11-24, OI-3). Before sending a request that came from an outside link, the viewer first
    asks the bridge for the mark of the name and sends the real request only if the answer is look-only. If the
    bridge's answer is does-something, is missing, or cannot be read, the viewer refuses the link and says why. The
    query is one request and counts against the person's allowance. The bridge answers it from the decision of its
    TRUST node. The query's form is to be defined on the BEES side.

## 6. Replies and the command vocabulary

1. A reply is a list of commands, carried out in the order given.
2. A command is a tagged tuple of two elements: an atom that says which command it is, and one map that holds its
   values, for example `{heading, #{into => <<"main">>, level => 1, text => <<"Nodes">>}}` (ruled 2026-11-24, OI-16;
   a mixed list of commands cannot be a list of bare maps in Silica). Each command has a stated set of keys in its
   map. A new optional key may be added to the map without breaking an old reader. A reader must not depend on the
   order of the keys in a map.
3. Names of commands and keys come from a fixed list with a version number, known to the viewer and to every
   program that builds or checks a reply. Everything an author supplies (text, region names, field names, addresses)
   is a byte string.
4. A reply states the vocabulary version it uses. The vocabulary, its version and the conformance set (section 14.1)
   live in this project. Servers that build replies take them from here.
5. Version 1 commands, as three levels, all required:
   - Level 1, text and action:
     - regions: make a named region inside another, clear, remove, replace the content of a region;
     - content: heading, paragraph, list and list item, quotation, preformatted text, a rule;
     - inline text: plain, emphasis, strong emphasis, code, link;
     - things the person acts on: link (go to an address), button (send a request), form with text fields, choice
       fields and tick boxes, and a submit action;
     - about the render: set the title, state the language, state the vocabulary version, say how long what was
       displayed may be kept.
   - Level 2: image, with a required text description. Images arrive in parts (section 8).
   - Level 3: table.
6. Content is placed by adding to the end of a region or by replacing a whole region. Editing in place and inserting
   at a position are not in version 1.
7. Behaviours a command may trigger in version 1: send a request for commands and carry out the reply; go to an
   address; send a request again after a time (section 9). A `cast` request is not in version 1.
8. Not in version 1: audio, video, a subscription, stored values, and anything that acts on the person's machine
   (copy to clipboard, save a file, notification, launching another application).
9. Appearance: commands say what a thing is. The viewer alone chooses fonts, colours and layout and follows the
   system's light and dark settings. A few hints (important, warning, success) are planned for a later version
   and are not part of version 1.

### 6.1 Checking a reply

1. Before anything is drawn or carried out, the viewer must decode the reply with bounds applied during decoding
   and check every command against the vocabulary and the limits in section 11. Terms that are not data (process
   identifiers, functions, references) must be refused.
2. A reply that fails is refused whole.
3. Unknown things:
   - an unknown action command, or a reply whose version is newer than the viewer's: refuse the whole reply and
     tell the person the page needs a newer viewer;
   - an unknown display command: use the fallback the author supplied, otherwise skip it with a visible note that
     something was left out.
4. A command that lacks required accessibility information (section 10) is refused or shown with a visible mark.

## 7. Assembling a render

1. A first reply may display a frame of named regions and name the further requests to send to fill them.
2. A reply to a request tied to a region may apply only inside that region.
3. Each region appears as its reply arrives. A region still waiting shows a "loading" mark. A region that failed
   shows "could not be fetched" with a "try again" control.
4. There is no automatic retry of a failed region.
5. When two replies target one region, the reply to the latest request wins.
6. The viewer keeps the current display and its named regions. Commands act on that state. It lasts until the
   viewer goes to another address in that tab.
7. The number of automatic requests for one render and the number of parts loading at once are bounded
   (section 11).

## 8. Images

1. An image has a required text description.
2. An image larger than one frame is requested in parts: a stated range of a named object, repeated until complete.
3. A total size cap applies. Above it the viewer shows a "too large" mark instead of the image.
4. The size of one part waits for the timing trial (section 14).

## 9. Timed refresh

1. A command may ask the viewer to send a stated look-only request again for a region after a stated time.
2. The viewer enforces a minimum interval (section 11).
3. A region that contains a field the person has edited must never be refreshed.
4. Each refresh is a request and counts against the person's allowance at the bridge.

## 10. Accessibility

1. An image without a text description, and a form field without a label, are refused or shown with a visible mark.
2. A render states its language.
3. Commands map to the standard SwiftUI controls (which are macOS controls underneath) so that VoiceOver, keyboard navigation, dark mode and system text
   size work without effort from the author. The viewer must pass the text descriptions and labels to the
   operating system's accessibility interface.
4. The person must be able to select and copy displayed text with the standard macOS shortcut. This is a feature
   of the text controls and is not a command.

## 11. Limits (all configurable)

Every limit in this table must be a configuration value, not a constant in the code. These are the starting values.

| Limit | Starting value |
|---|---|
| Commands in one reply | 2,000 |
| Nesting depth of a screen | 32 |
| Length of one text value | 64 KB |
| Total image size | 5 MB |
| Minimum timed-refresh interval | 5 seconds |
| Automatic requests for one render | 20 |
| Parts loading at once per tab | 4 |
| Default port | 481 |
| Message payload and reply body (`b`) | 16,384 bytes (the protocol ceiling; a lower value may be configured) |
| Message topic | 1 to 32 bytes (protocol bounds; fixed) |
| Messages accepted per sender per minute | 10 |
| Stored messages | 1,000 (oldest dropped) |
| Listening port | fixed, configurable (no starting value chosen: OI-23) |

The viewer must check these against the configuration at the point of use. There is no limit on the number of tabs for now (ruled 2026-11-24). Section 15 lists limits not yet given values
(requests per interval). The messaging limits above are node-wide or per-sender limits of the viewer's own; the node-wide
bounds of the library (messages handled at once, messages per interval) are start values of the library and are also
configurable.

## 12. Keeping, history and tabs

1. A reply may be kept only if it holds display commands only, only for the time its commands state, and only for a
   look-only request. With no statement, nothing is kept. A kept copy never re-runs an action.
2. When the network cannot be reached, the viewer may show a kept copy, clearly marked as old.
3. Each tab has its own display, history and regions. History offers Back and Forward. Back uses a kept copy where
   one is allowed and otherwise asks the node again. A form is not restored. An action is never repeated by going
   back.
4. Version 1 has tabs. All tabs on one network share one key and one allowance at the bridge, so the viewer must
   count requests across tabs and slow down together.
5. There are no stored values in version 1 (no cookie-like feature). A node identifies the person by their key.

## 13. What the window shows

1. The window always shows the name the person gave the network and the host.
2. A details panel shows the fingerprint of the network's producer key.
3. The viewer does not show which bridge answered, because the host names one bridge.
4. Pass expiry (section 4) is visible in the network list.

### 13.1 Application shell (ruled 2026-11-24)

Version 1 includes, as standard Mac behaviour:

1. An address bar to type or paste a `tempus://` address, with the network name and host beside it, and tabs in the
   system window tab bar. There is no cap on the number of tabs for now.
2. A network list window to add a network by importing a file, name it, and see key fingerprints and pass expiry.
3. The menu bar and keyboard shortcuts (new tab, close tab, reload, back, forward, copy).
4. Find in page: a search of the text of the current screen.
5. A messages view (section 18.5), reached from the sidebar of the application window or its tab bar, with a badge showing the
   number of unread messages. There are no system notifications.
6. Settings: per network, receiving messages on or off (off by default), accepted sender types, the listening port, the
   advertised address, the rate and the stored cap (section 18.6). The settings are in the network list window or the
   application's settings window; which one is open (OI-7).

The exact menus and shortcut keys are still to be written down.

## 14. Verification

1. **Conformance set.** From the start there is a fixed set of example replies with their expected results: valid
   replies, unknown commands, version mismatches, oversized text, too many commands, excess nesting, missing
   descriptions and labels, and non-data terms. Every implementation of the checker is tested against it.
2. **Golden trials.** The parts that do not draw (address parsing, reply checking, region assembly, tab and history
   logic, limit handling, pass expiry) are tested in the Silica trial style, with `.scout` golden outputs.
3. **Window checks.** The window itself is checked by hand, with a written checklist.
4. **Command-line trial, first.** Before the window is built, a small program sends a request to one bridge, checks
   the commands and prints what it would display and do. It also measures the time of real requests, one at a time
   and several in turn, and of image parts. Its numbers decide connection reuse (section 5.8) and the part size
   (section 8.4).
5. **Messages.** The conformance vectors of the messages proposal (`proposals/tempus-node-messages.md` 4.3) are run against the
   library reader the viewer uses. The accept rules, block list, rate and stored cap are tested as golden trials. See 18.9.
6. **Test network.** The viewer, the command-line trial and the window checks run against a test network built
   from BEES and the Silica compiler: one bridge, several TRUST nodes and several TEMPUS nodes. The TRUST nodes
   export the functions that return commands, and one of them decides each published name's mark (requirement
   5.2). The bridge's configuration is compiled in for now, as BEES does today, so changing a token, a whitelist
   entry or a permission means a rebuild. The network uses BEES's test-only keys and passes (requirement 4.4), and the viewer's own key is given a pass and an edge token by the test-only tool
   (requirements 4.9 and 18.3). The
   model for it is `project-bees/trials/c3_tempus_bridge` (a TRUST node, two bridges, and clients).

## 15. Open items (not requirements)

These were not ruled and must be decided before or during the build.

- OI-1. RULED 2026-11-24: the default port is 481 (requirement 3.7).
- OI-2. (Narrowed 2026-11-24.) The first network to test against is the test network of requirement 14.5. A real
  network is still open.
- OI-3. RULED 2026-11-24: the bridge sends the mark, a non-bridge TRUST node decides it, and the viewer asks the
  bridge first (requirement 5.11). The options considered were: ask the bridge first (chosen), a list read when a
  network is added, and the bridge refusing by itself. Still to be defined on the BEES side: the form of the query.
- OI-4. RULED 2026-11-24 (changed the same day): no cap on tabs for now. The earlier cap of 8 is removed. All tabs on one
  network still share one allowance at the bridge (requirement 12.4), and with no cap that shared counting and the
  viewer's own slowing down are the only protection. A cap may be added if the timing trial shows the bridge's
  limits are reached by ordinary use. The bridge's limits were designed for programs, not people clicking.
- OI-5. Whether the bridge may keep a connection open for several calls from one admitted peer. Decided after the
  trial in section 14.4.
  Measured 2026-11-24 (testnet/README.md "Timing trial", testnet/results/timing-20261124.md; loopback, not a ruling): a full
  request is about 11 ms, of which connect + TLS + admission is 4.3 ms (38 percent; it is CPU); the call itself is the rest.
  The client waits 5 round trips before it can send the call (TCP 1, TLS 1, admission 3) and 1 more for the call, so on a real path
  one call per connection costs 6 round trips against 1 with reuse (at 100 ms RTT: 600 ms against 100 ms). The measured advice is to
  allow reuse; the owner decides. The bridge as built also refuses at 3 or more connections at once.
- OI-6. (Narrowed 2026-11-24: passes are BEES's test-only ones for now, and no issuing tool is built.) Still open:
  the format for importing a network and a pass. RULED 2026-11-24: a file in ETF, with no private key (requirement
  4.2). A pasteable code may be added later. The exact layout of the term is still to be written down.
- OI-16. RULED 2026-11-24: a command is a tagged tuple carrying one map (requirement 6.2). Found by the test network
  (`testnet/experiments/etf-commands`): a command cannot be a bare map in Silica, because a sum may hold at most one
  record variant (error E2404). Stock Erlang decodes the tagged form.
- OI-17. RULED 2026-11-24: all arguments are byte strings (requirements 3.5, 5.6 and 5.10). Found by the test network: a TRUST
  export declares `args <ElemType>`, one element type for the whole argument list, so the bridge's MFA table cannot
  type mixed arguments. A number or true/false is written as text and the function reads it; a form is a flat list
  of alternating names and values. No change to BEES's MFA table is needed. The Swift `callFrame` still has to
  take byte strings.
- OI-18. RULED 2026-11-24: accepted (requirement 2.9). The release compiler's binaries do not carry the standard
  library units; their sources are taken from the Silica repository at the release tag's commit.
- OI-19. FOUND 2026-11-24 by the first test-network slice: every command is a tuple (requirement 6.2), and BEES's example
  clients cannot decode tuples. The Python client returned `refused ... bad_tag` for a good result frame. The Swift
  library, which the viewer uses in place (requirement 2.7), has a `Term` type with no tuple case, and its comment at
  `Frames.swift:270` says a frame with a tuple is refused and its bytes are kept in the `Outcome` (read in the source,
  not run). The viewer therefore needs the Swift library's ETF reader to decode tuples, which is a fix or extension
  made in BEES, in place. Until then the viewer can take the raw bytes from the `Outcome` and decode them itself.
- OI-11. Whether the Silica TCP carrier resolves domain names, or only the Swift host does. Requirement 3.3 puts
  resolution in the Swift host, so this matters only if Silica code ever dials directly.
- OI-14. RULED 2026-11-24: the latest macOS version only. The build machine's SDK is macOS 26. Older versions are not
  supported, and the document need not describe their differences.
- OI-15. Answered by reading the macOS 26 SDK's SwiftUI interface on 2026-11-24 (symbols present only; none was run
  yet, so each row is confirmed by the first spike). Plan, with no wrapped native control assumed:
  - Tables: SwiftUI `Table`.
  - Find in page: SwiftUI `findNavigator(isPresented:)`; whether it searches custom views, and not only text
    editors, is to be confirmed.
  - Selecting and copying text: `textSelection(_:)` per text element. Selection across several elements is not
    assumed. If it is wanted, a read-only `TextEditor` over attributed text is the fallback.
  - Tabs: RULED 2026-11-24: the system window tab bar, so the person keeps the standard Mac behaviour (drag a tab
    out to its own window, merge windows, the Window menu). With no cap, no wrapped control is needed
    for tabs. The state of each tab stays in the app's state store, keyed by the window, so a tab dragged to a new
    window keeps its display and history. The spike must show that this holds.
  - Menus and shortcuts: SwiftUI `commands`.
  Any control that the spike shows SwiftUI cannot supply is added to requirement 2.3's list of wrappers.
- OI-12. ANSWERED 2026-11-24 by the spike in `spikes/oi-12`: yes. Security.framework has no Ed25519 key type, so the
  key is kept as its 32-byte seed in a generic password item, and the library builds its identity and certificate
  from the seed in memory. Shown: the seed round-trips through the Keychain, CryptoKit and OpenSSL agree on the key,
  and a real TLS 1.3 handshake and admission succeed with the Keychain-held key. Still open: whether to use the
  file-based login keychain (worked) or the data-protection keychain (refused for an unsigned build, -34018), which
  depends on code signing; and access from a rebuilt or re-signed binary, untested. Also found: the library's
  `dial` requires the dialer to carry an advertised `host:port`, and a test pass for the viewer's own key can be made
  from the library's public calls, which is how requirement 4.9 now works. Since the messages ruling this matters for the
  listener as well: the viewer's advertised `host:port` is what other nodes dial (section 18.4).
- OI-13. ANSWERED 2026-11-24 by the spike in `spikes/oi-13`: yes. The Silica program's entry symbol is `main`
  (no underscore), so it links into a Swift executable and runs on a thread the host creates, while a SwiftUI
  application keeps the main thread. Events reach Silica through a blocking FFI worker that reads a C queue (no call
  into the runtime is needed), and commands reach Swift through an FFI worker that calls a C function, which calls
  a Swift handler. 200 round trips through three actors and two FFI workers: median 0.158 ms, maximum 1.6 ms. A
  burst of 5000 events came back complete and in order. Not yet shown: a real mouse click, a failing actor being
  restarted inside the embedded process, and an orderly shutdown. Silica's fault handler takes every fatal signal
  and exits with 70, so macOS writes no crash report (the spike's README lists the details).
- OI-7. RULED in part 2026-11-24: the application shell is in section 13.1. Still open: the exact menus and
  shortcut keys, the window layout, and the tests for the Swift C interface.
- OI-8. SETTLED 2026-11-24: the scheme is `tempus` and is the only link type allowed.
- OI-9. The total image cap of 5 MB is accepted as a configurable starting value. The size of the part waits for the
  timing trial. The test network shows that the largest
  part that fits one frame is about 131000 bytes, not 131072.
  Measured 2026-11-24 (testnet/README.md "Timing trial"; loopback, not a ruling): a request costs about 11 ms fixed and about
  0.1 ms per KB more; a 16 KB part takes 13.4 ms, 65 KB 18.2 ms, 131000 B 25.7 ms; the 234 KB image takes 49 ms in 2 parts. The
  measured advice is to keep 131000 bytes as the default and to fetch parts one or two at a time, because the bridge as built
  refuses at 3 or more connections at once; the owner decides.
- OI-10. RULED 2026-11-24: they live in this project (requirement 6.4).

- OI-20. OPEN (found 2026-11-24 while folding in the messages rulings): real-clock tokens for nodes. BEES has no real clock for
  a sentinel or bridge, only the fixed test clock driven by `clock` frames (messages proposal 3.10; not verified beyond that
  document). The viewer's edge token and bridge pass are judged by other nodes' clocks, so on a real network the expiry of the
  edge token is not judged until BEES has one. Until then the viewer can join only a test network.
- OI-21. OPEN: the macOS firewall and the incoming-connection prompt, and the entitlements (App Sandbox network server
  entitlement, code signing) that a listening app needs. OM-17 says macOS asks the person to allow incoming connections; none of
  this has been tried. It needs a spike like OI-12 and OI-13, and depends on how the app is signed (OI-12).
- OI-22. OPEN: how the viewer gets an edge token in a real network. For now a test tool signs it (requirement 18.3). A real
  network owner has no tool for it (the same gap as for passes, OI-6), and the form in which the person sends the key and
  receives the token, and the token's lifetime, are not decided. Whether the edge token and the bridge pass may be one file
  to import is not decided.
- OI-23. OPEN: use of the Swift library's listener and gossip peer inside the app: which library calls start and stop the
  listener and the peer, how their threads and the shuffle timers fit with the SwiftUI main thread and the Silica FFI workers
  (requirement 2.4), the default fixed port, how the LAN address is found and kept up to date when the machine's network
  changes, and what happens at sleep and wake. Not tried.
- OI-24. OPEN, BEES work: the message frame (kinds 15 and 16), the connection actor changes, the node's application message,
  and the Swift library's send-message wrapper and listener handler hook, as in `proposals/tempus-node-messages.md` sections 4.1
  and 4.2. Nothing is built. The viewer's messaging cannot be built until the Swift part exists. Also not yet fixed: the
  library's own node-wide bounds and their start values.
- OI-25. OPEN: changes to the test network so a node can message the viewer: an edge token for the viewer's key, a sentinel and
  edges that run the message handler, and checks of both directions (messages proposal section 5). The viewer's listener must
  be reachable from the test network's nodes on the same machine (loopback or the LAN address), which also needs OI-23.

## 16. Dependencies on other work

- BEES (`/Users/yenrab/project-bees`): the Swift TEMPUS client library, used in place and not copied; the update of
  its `callFrame` (requirement 5.10); fixes to it as bugs are found; the bridge, TRUST and TEMPUS nodes for the test
  network; and any change that OI-3 or OI-5 requires; and the message frame, the Swift send-message wrapper and listener
  handler hook, and the test network changes for messages (OI-24, OI-25).
- Silica (https://github.com/Silica-Language-and-Compiler/silica): FFI to a C interface (present in
  `trials/ffi_addition`), actors, supervisors, and the compiler binaries from its releases (requirement 2.9).
- A Swift host with a C interface for the window, the controls, the Keychain, the listener and the messages, linked with
  the Swift client library.
- Network owners who publish names with marks, publish passes outside the network, and issue edge tokens to viewers
  that are to receive messages.

## 17. Out of scope for version 1

Other platforms, audio and video, live subscriptions, stored values, actions on the person's machine, appearance
control, editing in place, bridge discovery, automatic pass renewal, guest access, a naming service, and any link
scheme other than `tempus://`. For messages: NAT traversal, relay or store-and-forward (nothing carries a message for a
sender), receiving while the app is closed, keeping messages after the app quits, system notifications, a per-message
signature, group messages, connection reuse and a persistent channel, commands carried by messages, and carriers other than
TLS 1.3 over TCP.

## 18. Messages (ruled 2026-11-24)

Source: the rulings OM-1 to OM-19 in `proposals/tempus-node-messages.md`, which holds the wire definition. Nothing here is
built, and the BEES side is not built either (OI-24).

### 18.1 Sending

1. The viewer must be able to send one message to one node: a message names the recipient's key (its peer id, the SHA-512 of its
   public key), carries a topic (opaque bytes, 1 to 32) and a body (0 to 16,384 bytes), and is sent through the Swift library on
   its own TLS 1.3 connection. It is one message per connection: one request and one reply, then close.
2. After admission the viewer must check that the connected node's id is the recipient's id, and close without sending if it
   is not.
3. The person sends by a compose form: recipient key and address, topic, body. The form shows the reply, or "not delivered".
   "Not delivered" is all the viewer can say, because a refusal, a dead address and a timeout look the same.
4. The recipient is found from the replies to a sample request and from the descriptors of messages received. There is no
   directory and no store reading call. The person may also type a key and address.
5. A message is never sent automatically, on a timer or from a command in a reply. It is sent only when the person acts.
   Nothing is relayed or stored for later delivery.

### 18.2 Receiving and the listener

1. While the app is open and receiving is on for at least one network, the viewer must listen on a fixed port (configurable)
   (OM-17). It must stop listening when the app quits, and it receives nothing then.
2. Receiving is off by default, set per network. With receiving off for a network the viewer refuses every message for it
   by closing without a reply.
3. The accepted sender types are chosen by the person per network, none by default. Any admitted peer may try to send; the
   viewer's accepted set decides (OM-5).
4. A sender may be blocked by key. A message from a blocked key is refused by closing.
5. A per-sender rate (default 10 a minute) applies, and a message over it is refused. These are the viewer's own limits; the
   library's node-wide bounds apply as well (OM-8, OM-12).
6. The viewer must check a received message against the protocol's bounds (a map of the fixed keys in name order, topic 1 to 32
   bytes, body up to 16,384 bytes, `to` equal to its own id) and refuse one that fails, by closing with no reply.
7. The viewer replies to a message with an empty body as acknowledgement, unless the owner rules otherwise. It does
   not deduplicate by library; if it shows the same message twice because of a retry, that is how it behaves (OM-6).
8. No message is delivered while the viewer is closed. NAT and a closed firewall make the viewer unreachable, and v1 does nothing
   about that (OM-15).

### 18.3 Gossip membership and the edge token

1. The viewer joins gossip as an edge (OM-19): it asks a sentinel, is inserted into the edge store, and other nodes learn its
   address by shuffling. It runs the join and the shuffle timers and keeps the three stores through the Swift library.
2. The viewer's key needs an edge token, issued by the network owner for that key, in addition to its bridge pass. Both are held.
   The network list shows the expiry of both. The viewer must warn before the edge token expires, as for a pass (requirement 4.5).
3. In the test network the edge token is signed for the viewer's own key by the test-only tool of requirement 4.9, with the
   test producer seed, and must not appear in a production build.
4. The viewer joins gossip only for a network that has a sentinel in its network file (whether it also requires receiving to be on is not ruled).
   The network file's layout for a sentinel and an edge token is not yet written (OI-6, OI-22).

### 18.4 Advertised address

1. The viewer advertises one `host:port` that other nodes dial. The person may edit it. Its default is the machine's LAN
   address and the configured fixed port.
2. The advertised address is a claim. The viewer must show it, say that it may be unreachable, and say that the viewer cannot
   tell whether it is reachable (no NAT handling in v1, OM-15).

### 18.5 Messages view

1. A messages view lists received messages newest first: network, sender key fingerprint, topic, time, and a preview. A message
   opens to show the full body as text.
2. A badge and a count in the tab bar or sidebar show unread messages. There are no system notifications.
3. The body is shown as plain text only. It is never interpreted: no link in it is followed or opened for the person, no
   `tempus://` address in it is opened automatically, and no image or markup is drawn.
4. Messages are kept in memory only, while the app is open (OM-18). At most the stored cap (default 1,000) are kept; the oldest
   is dropped. Nothing is written to disk.
5. From a message the person may block its sender's key, or start a reply in the compose form with the sender's descriptor, which
   is usable only if its address works (3.4 of the proposal).

### 18.6 Controls

Per network: receiving on or off (default off), accepted sender types (default none), the blocked keys. For the viewer: the
listening port, the advertised address, the per-sender rate, and the stored cap. All of these are configuration values
(section 11), and the rate and the cap are limits of section 11.

### 18.7 Security posture

1. A message is data to show. No command is executed from a message (OM-16, requirement R3). A message holds no
   command vocabulary, and the viewer must not pass a message body to the command checker or to the address parser.
2. Admission is the only authentication. A message has no signature of its own (OM-10). The sender shown is the key proved by
   admission, and the viewer shows its fingerprint and no name the sender chose.
3. The listener is open only while the app is open, only for networks with receiving on, and refuses by closing with no reason.
4. A flood is limited by the per-sender rate, the stored cap, the library's node-wide bounds and the connection deadline. A
   peer with many valid tokens can still fill the view up to the cap.
5. A message received from one network is shown under that network and never changes state of another (requirement 4.8).

### 18.8 Consequences elsewhere

- Application shell: the messages view and badge, the settings (requirement 13.1, items 5 and 6).
- Keychain: one seed per network serves both roles (requirements 4.3 and 4.7).
- Test passes: the test tool also signs an edge token for the viewer's key (requirement 4.9).
- Architecture: a listener and a gossip peer in the Swift host, with the message store in the host's observable state (2.3,
  2.8). They must not block a window (2.6).

### 18.9 Conformance and verification

1. The vectors of `proposals/tempus-node-messages.md` section 4.3 (valid and refused, keys out of order refused) are run
   against the reader the viewer uses, and the viewer's builder produces the bytes of V1 to V4 for the same inputs.
2. The accept rules, the block list, the per-sender rate and the stored cap are golden trials of the Silica or Swift part that holds them.
3. The window parts (messages view, compose form, settings) are on the written checklist of 14.3.
4. The test network of 14.6 has a node that sends the viewer a message and the viewer sends to an edge (proposal section 5).
