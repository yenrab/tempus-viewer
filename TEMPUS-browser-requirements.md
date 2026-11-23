# TEMPUS browser: requirements

Status: first draft, written 2026-11-23 from an interview with the owner. It follows
`TEMPUS-browser-design.md` (the design notes, which hold the options considered and the BQ numbers cited here). Every
requirement below was either ruled by the owner in the interview or is a stated consequence of a ruling. Where the
owner has not ruled, the item is in section 15 and is not a requirement.

Wording: "must" is a requirement. "Should" is a strong preference that may be dropped with a reason. "The browser" is
the new native application, not a web browser.

## 1. Purpose and scope

1. The TEMPUS browser is a native macOS application, written in Silica, that a person uses to visit places on TEMPUS
   networks. It does not use HTTP or HTTPS.
2. It sends a request to a bridge. The reply is a list of commands. The browser carries the commands out as native
   macOS controls.
3. It is a general tool. No first application is chosen. Test applications are written as needed.
4. Version 1 is for public networks, with admission as in section 4.
5. Version 1 runs on macOS only.

### 1.1 Rulings carried over from the design document

- R1. The unit is a command, not a page.
- R2. One render may be built from more than one request. The frame size therefore does not limit a render.
- R3. No reply holds code. A command is data that selects a behaviour the browser already has. No command carries a
  condition, loop, expression, template with logic or reference to code to load.

## 2. Architecture

1. The browser is a Silica application designed to Silica principles: a root supervisor, a supervision tree of
   whatever depth suits, many actors each with one responsibility, and `cast` in preference to `call` wherever
   possible.
2. Windowing and drawing use native macOS widgets (AppKit). Silica does not call AppKit directly. A Swift host
   exposes a C interface, and Silica reaches it by FFI through guarded worker actors (the pattern in
   `silica/trials/ffi_addition`).
3. The Swift host owns the main thread and the AppKit run loop. It applies drawing commands on the main thread.
4. Events (clicks, keystrokes, window changes) travel from the Swift host into Silica by calls to a C entry point.
   Each becomes a cast to a supervised listener actor. The host never waits for a reply. A failed listener must be
   restarted by its supervisor.
5. Drawing travels the other way. A window actor casts a command to an FFI worker, which passes it to the host.
6. Network work must never freeze a window.
7. Networking, TLS 1.3 with X25519MLKEM768, Ed25519 and admission are provided by BEES. The browser is an ordinary
   edge peer and needs no new kind of token and no change to admission.
8. The browser must be built from separate responsibilities at least along these lines (names are indicative):
   network store, key store, address parsing, request sending, reply checking, render assembly, tab, history, kept
   copies, window, event listening, refresh timers.

## 3. Addresses and links

1. The only link scheme the browser accepts is `tempus://`. Every other scheme must be refused, wherever it appears:
   in the address entry, in a command, in a pasted link, and in a request from the operating system.
2. The form is `tempus://host[:port]/name?arguments`.
3. The host is a domain name or an IP address. It identifies one specific bridge. The browser connects to that host
   and port. There is no discovery of other bridges in version 1.
4. `name` is a name that the network owner published. The application maps it to a function. Raw module and
   function names must not be accepted in an address.
5. Arguments are byte strings (text), whole numbers and true/false only, so an address can be copied, sent and
   bookmarked.
6. An address names only the first request of a render. Later requests come from commands and need no text form.
7. The default port is not yet ruled (section 15).

## 4. Networks, keys and passes

1. The browser may contact a host only for a network the person has added. A link to a host that belongs to no
   added network must produce a clear message that the network has not been added, and no connection is made.
2. Adding a network is a step in the browser. The person supplies what the network owner publishes outside the
   network (the producer's key, a label, and the host or hosts). The person gives the network a name.
3. The browser holds one Ed25519 key per network. Keys are made by the browser.
4. Admission is by a per-person pass. The browser shows the public half of the key for that network so the person
   can send it to the network owner. The owner returns a pass signed for that key. The person imports it.
5. The pass lifetime is judged by the bridge on its own clock. The browser must record each pass's expiry, warn the
   person before it expires, and say plainly when it has expired and offer the import step again.
6. Automatic renewal of a pass, a guest tier, and an open token endpoint are not in version 1. Networks that want
   public access publish the means of getting a pass outside the network.
7. Private keys must be stored in the macOS Keychain.
8. State is separate for each network, with no exception.

## 5. Requests

1. A request is made with `call` through a bridge, using the existing BEES protocol.
2. Every published name carries one of two marks: look-only or does-something. The network owner sets the mark.
3. A link from outside the browser (pasted, from another application) may open only a look-only name. A
   does-something name must refuse to run from an outside link, and runs only when the person acts inside the
   browser, for example by pressing a button.
4. Only look-only requests may be sent automatically, refreshed on a timer, or kept for reuse.
5. A command may name requests only on its own network.
6. A form sends its fields as one map argument. Values are byte strings, numbers and true/false only. The
   function must treat them as untrusted input.
7. A refusal, a failed function and a timeout look the same to the client. The browser must show one message,
   "could not be fetched", in the region that was waiting. A function that ran and wants to report a problem does so
   by returning display commands.
8. Whether connection reuse is needed is decided after the trial in section 14. Until then the browser must work
   with one request per connection.
9. The browser must slow down by itself when it is refused, and must not exceed the limits in section 11.

## 6. Replies and the command vocabulary

1. A reply is a list of commands, carried out in the order given.
2. A command is a map with one key that says which command it is, plus its values. Each command has a stated set of
   keys. A new optional key may be added without breaking an old reader.
3. Names of commands and keys come from a fixed list with a version number, known to the browser and to every
   program that builds or checks a reply. Everything an author supplies (text, region names, field names, addresses)
   is a byte string.
4. A reply states the vocabulary version it uses.
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
9. Appearance: commands say what a thing is. The browser alone chooses fonts, colours and layout and follows the
   system's light and dark settings. A few hints (important, warning, success) are planned for a later version
   and are not part of version 1.

### 6.1 Checking a reply

1. Before anything is drawn or carried out, the browser must decode the reply with bounds applied during decoding
   and check every command against the vocabulary and the limits in section 11. Terms that are not data (process
   identifiers, functions, references) must be refused.
2. A reply that fails is refused whole.
3. Unknown things:
   - an unknown action command, or a reply whose version is newer than the browser's: refuse the whole reply and
     tell the person the page needs a newer browser;
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
6. The browser keeps the current display and its named regions. Commands act on that state. It lasts until the
   browser goes to another address in that tab.
7. The number of automatic requests for one render and the number of parts loading at once are bounded
   (section 11).

## 8. Images

1. An image has a required text description.
2. An image larger than one frame is requested in parts: a stated range of a named object, repeated until complete.
3. A total size cap applies. Above it the browser shows a "too large" mark instead of the image.
4. The size of one part waits for the timing trial (section 14).

## 9. Timed refresh

1. A command may ask the browser to send a stated look-only request again for a region after a stated time.
2. The browser enforces a minimum interval (section 11).
3. A region that contains a field the person has edited must never be refreshed.
4. Each refresh is a request and counts against the person's allowance at the bridge.

## 10. Accessibility

1. An image without a text description, and a form field without a label, are refused or shown with a visible mark.
2. A render states its language.
3. Commands map to the standard macOS controls so that VoiceOver, keyboard navigation, dark mode and system text
   size work without effort from the author. The browser must pass the text descriptions and labels to the
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

The browser must check these against the configuration at the point of use. Section 15 lists limits not yet given
values (tab count, requests per interval).

## 12. Keeping, history and tabs

1. A reply may be kept only if it holds display commands only, only for the time its commands state, and only for a
   look-only request. With no statement, nothing is kept. A kept copy never re-runs an action.
2. When the network cannot be reached, the browser may show a kept copy, clearly marked as old.
3. Each tab has its own display, history and regions. History offers Back and Forward. Back uses a kept copy where
   one is allowed and otherwise asks the node again. A form is not restored. An action is never repeated by going
   back.
4. Version 1 has tabs. All tabs on one network share one key and one allowance at the bridge, so the browser must
   count requests across tabs and slow down together.
5. There are no stored values in version 1 (no cookie-like feature). A node identifies the person by their key.

## 13. What the window shows

1. The window always shows the name the person gave the network and the host.
2. A details panel shows the fingerprint of the network's producer key.
3. The browser does not show which bridge answered, because the host names one bridge.
4. Pass expiry (section 4) is visible in the network list.

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

## 15. Open items (not requirements)

These were not ruled and must be decided before or during the build.

- OI-1. Default port for `tempus://`.
- OI-2. A first real network to test against.
- OI-3. How the look-only or does-something mark reaches the browser before it sends a request from an outside
  link. Sending first and checking after is unsafe. Options: the application publishes a list of names with marks
  that the browser reads when a network is added; the mark is part of the address; or the bridge refuses
  does-something names from untrusted origins. This needs a BEES-side answer.
- OI-4. Maximum number of tabs, and how the per-peer allowance at the bridge is divided among them. The bridge's
  limits were designed for programs, not people clicking.
- OI-5. Whether the bridge may keep a connection open for several calls from one admitted peer. Decided after the
  trial in section 14.4.
- OI-6. Text of the pass and network import format (a file, a code, or both).
- OI-7. Exact extra tests for the Swift C interface, and how much of AppKit the first version maps (window layout,
  menus, keyboard shortcuts are not yet specified).
- OI-8. The scheme is fixed as `tempus`. The owner may still rename it.
- OI-9. The size of the part for image requests, and the exact total image cap (5 MB is a starting value).
- OI-10. Whether the reference replies and vocabulary version live in the BEES repository or here.

## 16. Dependencies on other work

- BEES: the client code and admission, and any change that OI-3 or OI-5 requires.
- Silica: FFI to a C interface (present in `trials/ffi_addition`), actors, supervisors, TCP and TLS as provided
  through BEES.
- A Swift host with a C interface for the window, the controls and the Keychain.
- Network owners who publish names with marks and publish passes outside the network.

## 17. Out of scope for version 1

Other platforms, audio and video, live subscriptions, stored values, actions on the person's machine, appearance
control, editing in place, bridge discovery, automatic pass renewal, guest access, a naming service, and any link
scheme other than `tempus://`.
