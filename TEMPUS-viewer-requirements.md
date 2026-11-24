# TEMPUS viewer: requirements

Status: first draft, written 2026-11-23 from an interview with the owner. It follows
`TEMPUS-viewer-design.md` (the design notes, which hold the options considered and the BQ numbers cited here). Every
requirement below was either ruled by the owner in the interview or is a stated consequence of a ruling. Where the
owner has not ruled, the item is in section 15 and is not a requirement.

Revision 2026-11-24: after reading `project-bees` and `silica` the owner ruled on the points in section 15 (OI-3
partly, OI-6, the network client, call arguments, the test network, passes, domain names, the compiler). Those
rulings are folded into sections 2, 3, 4, 5, 14, 15 and 16.

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
4. Events (clicks, keystrokes, window changes) travel from the Swift host into Silica by calls to a C entry point.
   Each becomes a cast to a supervised listener actor. The host never waits for a reply. A failed listener must be
   restarted by its supervisor.
5. Drawing travels the other way. A window actor casts a command to an FFI worker, which passes it to the host.
6. Network work must never freeze a window.
7. Networking, TLS 1.3 with X25519MLKEM768, Ed25519 and admission are provided by the Swift TEMPUS client library
   in `project-bees/example_tempus_clients/swift` (`TempusClient`), used as it is. It must not be copied into this
   project. It is a dependency, built from its own place. Bugs found in it are fixed there, in the BEES project.
   The viewer is an ordinary edge peer and needs no new kind of token and no change to admission.
   Silica actors drive it through the Swift host and the FFI workers of requirement 2.2: a request actor casts a
   request to an FFI worker, which calls the library and casts the outcome back.
8. The viewer must be built from separate responsibilities at least along these lines (names are indicative):
   network store, key store, address parsing, request sending, reply checking, render assembly, tab, history, kept
   copies, window, event listening, refresh timers.
9. Toolchain: the viewer, the bridge, the TRUST nodes and the TEMPUS nodes of the test network are built with the
   compiler that the link `silica/binaries/silica-compiler` names, and that link is always taken as the latest
   compiler found. No version is pinned in this project. The Swift host builds with the installed Swift and the
   installed OpenSSL (4.1.0 or later, as `project-bees/contract/what-is-required-to-use.md` requires).

## 3. Addresses and links

1. The only link scheme the viewer accepts is `tempus://`. Every other scheme must be refused, wherever it appears:
   in the address entry, in a command, in a pasted link, and in a request from the operating system.
2. The form is `tempus://host[:port]/name?arguments`.
3. The host is a domain name or an IP address, and both must work. It identifies one specific bridge. The viewer
   connects to that host and port, resolving a domain name in the Swift host (the library uses `getaddrinfo`). There
   is no discovery of other bridges in version 1.
4. `name` is a name that the network owner published. The application maps it to a function. Raw module and
   function names must not be accepted in an address.
5. Arguments are byte strings (text), whole numbers and true/false only, so an address can be copied, sent and
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
3. The viewer holds one Ed25519 key per network. Keys are made by the viewer.
4. Admission is by a per-person pass. The viewer shows the public half of the key for that network so the person
   can send it to the network owner. The owner returns a pass signed for that key. The person imports it.
   For now, passes are the test-only tokens that BEES makes from fixed seeds (`tools/bees_tempus_ids.py`). No tool
   for issuing real passes is built in this phase, and the test passes must never be treated as real ones.
5. The pass lifetime is judged by the bridge on its own clock. The viewer must record each pass's expiry, warn the
   person before it expires, and say plainly when it has expired and offer the import step again.
6. Automatic renewal of a pass, a guest tier, and an open token endpoint are not in version 1. Networks that want
   public access publish the means of getting a pass outside the network.
7. Private keys must be stored in the macOS Keychain.
8. State is separate for each network, with no exception.
9. Test mode. Because a pass is signed for one key and the test passes come from fixed test keys, a test build may load
   a fixed test key in place of the Keychain key. This switch must live in a unit that only test builds list, as BEES's
   test frames do. A production build must not contain it, and a check (as in BEES's `production-check`) must show
   that it does not.

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
6. A form sends its fields as one map argument. Values are byte strings, numbers and true/false only. The
   function must treat them as untrusted input.
7. A refusal, a failed function and a timeout look the same to the client. The viewer must show one message,
   "could not be fetched", in the region that was waiting. A function that ran and wants to report a problem does so
   by returning display commands.
8. Whether connection reuse is needed is decided after the trial in section 14. Until then the viewer must work
   with one request per connection.
9. The viewer must slow down by itself when it is refused, and must not exceed the limits in section 11.
10. The `call` frame must carry the arguments the viewer sends: byte strings (text), whole numbers, true/false,
    and one map (the form of requirement 5.6). The Swift `callFrame` today takes whole numbers only
    (`args: [Int64]`) and must be updated, in `project-bees`, to carry these. The Silica client's frame builder and
    the bridge's reading of arguments must be checked to agree, with the BEES conformance goldens extended to
    cover them.
11. Mark query (ruled 2026-11-24, OI-3). Before sending a request that came from an outside link, the viewer first
    asks the bridge for the mark of the name and sends the real request only if the answer is look-only. If the
    bridge's answer is does-something, is missing, or cannot be read, the viewer refuses the link and says why. The
    query is one request and counts against the person's allowance. The bridge answers it from the decision of its
    TRUST node. The query's form is to be defined on the BEES side.

## 6. Replies and the command vocabulary

1. A reply is a list of commands, carried out in the order given.
2. A command is a map with one key that says which command it is, plus its values. Each command has a stated set of
   keys. A new optional key may be added without breaking an old reader.
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

The viewer must check these against the configuration at the point of use. There is no limit on the number of tabs for now (ruled 2026-11-24). Section 15 lists limits not yet given values
(requests per interval).

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
5. **Test network.** The viewer, the command-line trial and the window checks run against a test network built
   from BEES and the Silica compiler: one bridge, several TRUST nodes and several TEMPUS nodes. The TRUST nodes
   export the functions that return commands, and one of them decides each published name's mark (requirement
   5.2). The bridge's configuration is compiled in for now, as BEES does today, so changing a token, a whitelist
   entry or a permission means a rebuild. The network uses BEES's test-only keys and passes (requirement 4.4), and the test build uses the fixed test key
   (requirement 4.9). The
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
- OI-6. (Narrowed 2026-11-24: passes are BEES's test-only ones for now, and no issuing tool is built.) Still open:
  the format for importing a network and a pass. RULED 2026-11-24: a file in ETF, with no private key (requirement
  4.2). A pasteable code may be added later. The exact layout of the term is still to be written down.
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
- OI-12. Whether an Ed25519 key can be held in the macOS Keychain in a form the Swift library's OpenSSL
  client certificate can use. The likely route is a stored raw key. This is unverified and is a spike of the
  first build step.
- OI-13. Whether the Swift host can own the main thread and the AppKit run loop while a Silica runtime runs
  beside it, with a Swift-to-Silica entry that casts an event to an actor. The host is a SwiftUI application, whose
  `App` entry point starts the run loop. The FFI trials show only Silica calling C. This is the first spike.
- OI-7. RULED in part 2026-11-24: the application shell is in section 13.1. Still open: the exact menus and
  shortcut keys, the window layout, and the tests for the Swift C interface.
- OI-8. SETTLED 2026-11-24: the scheme is `tempus` and is the only link type allowed.
- OI-9. The total image cap of 5 MB is accepted as a configurable starting value. The size of the part waits for the
  timing trial.
- OI-10. RULED 2026-11-24: they live in this project (requirement 6.4).

## 16. Dependencies on other work

- BEES (`/Users/yenrab/project-bees`): the Swift TEMPUS client library, used in place and not copied; the update of
  its `callFrame` (requirement 5.10); fixes to it as bugs are found; the bridge, TRUST and TEMPUS nodes for the test
  network; and any change that OI-3 or OI-5 requires.
- Silica (`/Users/yenrab/silica`): FFI to a C interface (present in `trials/ffi_addition`), actors, supervisors, and
  the compiler named by `binaries/silica-compiler`, always the latest found (requirement 2.9).
- A Swift host with a C interface for the window, the controls and the Keychain, linked with the Swift client
  library.
- Network owners who publish names with marks and publish passes outside the network.

## 17. Out of scope for version 1

Other platforms, audio and video, live subscriptions, stored values, actions on the person's machine, appearance
control, editing in place, bridge discovery, automatic pass renewal, guest access, a naming service, and any link
scheme other than `tempus://`.
