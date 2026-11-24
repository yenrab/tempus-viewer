# TEMPUS viewer: current thoughts and open questions

Status: a draft, first written on 2026-11-23 at the owner's request and revised the same day after the owner's
first rulings (section 1.1). Nothing is built. The questions are numbered BQ-1 onward so that a ruling can name one.
Each open question gives the options, what each costs, and a recommendation. A recommendation is the author's
opinion, not a decision.

## 1. The idea

A TEMPUS viewer is a native application that a person uses as they use a web browser, with these differences:

- It does not use HTTP or HTTPS. It sends a node a request the BEES protocols already have, and the node answers
  with one term in the External Term Format (ETF), the encoding BEES uses for every message.
- What comes back is not a page and not HTML. It is a list of commands. A command tells the viewer to display
  something or to do something. The viewer carries the commands out with the toolkit of the machine it runs on.
- What the person sees at one moment, called a render in this document, may be built from the commands of more
  than one request.

The word "viewer" here means this new application. It does not mean a web browser such as Safari or Chrome. A page
of JavaScript running inside a web browser cannot do this, because a web page cannot open the kind of connection the
protocols need. A native application can.

### 1.1 Rulings so far (owner, 2026-11-23)

- R1. The unit is a command, not a page. A reply to a request holds commands to be sent for display and to trigger
  behaviour in the viewer.
- R2. More than one request for commands may be sent for a single render. Because of this the size of one frame is
  not a limit on what a render can show.
- R3. There is to be no code in any response to a command request. A command is data that selects a behaviour the
  viewer already has. It is never a program, an expression or a script for the viewer to run. This closes BQ-1.

## 2. What exists today that the viewer can stand on

These are facts about Project BEES as of 2026-11-23, taken from its design documents and code.

- Connections. Every TEMPUS connection is TCP with TLS 1.3 on top. Both sides present a certificate whose key is an
  Ed25519 key, the key exchange group is X25519MLKEM768, and the application protocol is `tempus/1`. A peer is
  identified by its Ed25519 public key, and it is admitted when it shows a token that a producer signed for that key.
- A request that returns a term. A peer with an edge token can send a bridge node a `call` frame that names a module,
  a function and a list of arguments. The bridge runs the function on the TRUST network behind it and answers with a
  `result` frame that holds the function's return value, which is any term. This is the request for commands: the
  returned term is the list of commands.
- A request with no reply. A `cast` frame has the same form as a `call` and is never answered.
- Network code in several languages. Client code exists in Python, Swift, Kotlin and Silica and has been tested
  against real nodes. The Swift one could carry an application for Apple machines and the Kotlin one an application
  for Android or for a desktop. Extensions that are full nodes are being written in the same languages.
- Nothing exists for the command vocabulary, for carrying commands out, or for addresses. Those are the new work,
  and this document is about them.

## 3. Facts about today's protocol that shape the design

The viewer has to live with these, or a ruling has to change them.

1. One frame holds at most 131072 bytes. By ruling R2 this bounds one reply, not one render: a render that needs
   more is built from more requests. It still bounds any single thing that cannot be split, such as one image sent
   as bytes (BQ-7).
2. A bridge answers one call and then closes the connection. Every request for commands is a new connection with a
   new TLS handshake and a new admission. Ruling R2 makes this matter more, since one render may now need several
   (BQ-12).
3. A refusal has no text. When a bridge refuses a call, when the function fails and when the call times out, the
   client sees the same thing: the connection closes with no reply. The viewer cannot tell the person why commands
   did not come (BQ-19).
4. A bridge runs only the functions its application has exported, and only for the peer types its configuration
   permits. With no permission configured, nothing is permitted. So commands exist only where an application has
   chosen to publish a function that returns them.
5. A bridge scores each peer and limits how many requests a peer may send in an interval and have in progress at
   once. A render made of several requests, and a person who clicks quickly, both spend from those limits.
6. Every atom in a Silica program is fixed when the program is compiled. A node cannot make a new atom from bytes
   that arrive. Any part of the vocabulary that is written as atoms is therefore a fixed list that both sides know.
   This fits ruling R3 well: the set of commands is a closed list.
7. A token has a lifetime and the node judges it by its own clock. The viewer must hold a token for its key and
   refresh it.
8. The node sends nothing to a client that the client did not ask for. There is no message that says "something
   has changed".

## 4. First thoughts on the shape

These are starting positions, each tied to a ruling or to a question in section 5 or 6.

- A reply is a list of commands, carried out in the order given.
- There are two families of command. A display command puts something in front of the person or changes what is
  there: show a heading, add an item to a list, replace a named region, clear a region. A behaviour command makes
  the viewer do something that is not drawing: send another request, go to another address, send again after a
  time, keep a value. Which behaviours exist is BQ-8.
- A command is data (ruling R3). The viewer's behaviours are built into the viewer; a command chooses one and
  gives it values. No command carries a condition, a loop, an expression or anything else to be evaluated, and the
  vocabulary has no command whose meaning is "run this".
- All logic runs on the node. When the person acts (presses a button, submits a form), the viewer sends the
  request that the command which made the button named, and the reply is more commands.
- A render is assembled. The first reply may display a frame of named regions and tell the viewer which further
  requests to send to fill them. Each later reply's commands say which region they apply to. This is how ruling R2
  is met, and it needs rules for order and for requests that fail (BQ-20, BQ-21).
- The viewer therefore keeps state between replies: the current display with its named regions. A command acts on
  that state. This is the main difference from a page model, where each reply replaces everything.
- A command says what a thing is (a heading, a list, an action), and the viewer decides how it looks. A render
  made this way is usable on a phone, on a desktop and by a screen reader without the author doing anything.
- Each command is a small map with a key that says which command it is, in the same style as the protocol's own
  messages, which are maps with a key `t`.
- The vocabulary is a closed list with a version number. A viewer that meets a command it does not know has one
  stated behaviour.
- An address names a place to ask and what to ask for: which network, which function, which arguments. It has one
  text form that a person can copy, send and bookmark.
- The viewer is an ordinary edge peer. It needs no new kind of token and no change to admission.

## 5. Open questions: the command vocabulary

### BQ-1. Does a reply hold any program code? RULED

RULED (owner, 2026-11-23, ruling R3): no. There is to be no code in any response to a command request. The options
were (a) none, (b) a small fixed expression language, (c) a full scripting language; (a) is the ruling.

What follows from it, for the vocabulary to respect: no command may carry a condition, a loop, an expression, a
template with logic, or a reference to code to load. A display that depends on what the person does is produced by
a new request, never by something the reply told the viewer to work out. If renders feel slow because of this,
the answer is in the protocol (BQ-12), not in the vocabulary.

### BQ-2. How is a command written?

- a. A map with a key that names the command, as the protocol's messages are:
  `#{c => show_heading, in => <<"main">>, level => 1, text => <<"...">>}`.
- b. A tagged tuple: `{show_heading, <<"main">>, 1, <<"...">>}`.
- c. A list of pairs, in the style of some Erlang web libraries.

Cost: (a) is longer in bytes and matches the frames BEES already checks key by key; a new optional key can be added
without breaking an old reader. (b) is the shortest and the most natural to write in Erlang or Elixir, and adding a
field changes the size of the tuple, which breaks an old reader. (c) is in between.

Recommendation: (a), with the rule the protocol already has for its own maps: a stated set of keys for each command.
Whether an unknown key is refused or ignored is BQ-6.

### BQ-3. Are the names of commands and keys atoms or byte strings?

- a. Atoms.
- b. Byte strings.

Cost: with (a) the vocabulary is a fixed list compiled into every Silica program that builds or checks a reply
(fact 6). That is a strength for checking, it suits a closed list of commands (ruling R3), and it means a new
command needs a new build of those programs. With
(b) a node can pass on a name it does not know, at the price of comparing bytes and of looser checking.

Recommendation: (a) for the names the vocabulary defines, and byte strings for everything an author supplies (text,
names of regions and fields, addresses).

### BQ-4. Which display commands are in the first version?

The behaviour commands are BQ-8. A candidate list of display commands, to be cut or extended:

- regions: make a named region inside another, clear a region, remove a region, replace a region's content;
- content placed in a region: heading, paragraph, list and list item, table, quotation, preformatted text, a rule
  between parts;
- text inside a paragraph: plain text, emphasis, strong emphasis, code, a link;
- things the person acts on: a link (go to an address), a button (send a request), a form with fields (text,
  number, choice, tick box) and a submit action. Each names the request to send; none holds logic;
- media: image;
- about the render as a whole: set the title, state the language, state the vocabulary version, say how long
  what was displayed may be kept.

Sub-question: is content placed by adding to the end of a region only, or may a command insert at a position or
change one item in place? Adding and replacing a whole region are simple to make safe when replies arrive in any
order (BQ-20); editing in place is not.

Cost: every command is work in every viewer and a promise to keep. A list that is too small makes authors misuse
what there is.

Recommendation: start with regions, headings, paragraphs, lists, inline text, link, button, a form with text and
choice fields, and image, with adding and whole-region replacement only. Leave tables, audio, video and editing in
place for a later version.

### BQ-5. How much do commands say about appearance?

- a. Nothing. A command says what a thing is; the viewer chooses fonts, colours and layout.
- b. A small set of hints: importance, alignment, a named tone such as warning or success, light or dark preference.
- c. Full control: sizes, positions, colours, fonts, as CSS gives.

Cost: (a) makes every render look alike and makes brand design impossible; it is the cheapest to implement and the
best for accessibility. (c) is a layout engine, which is the largest single part of a web browser. (b) is a list
that will be argued over.

Recommendation: (a) for the first version, with (b) as the planned next step.

### BQ-6. What does a viewer do with something it does not know?

The cases are an unknown command, an unknown key in a known command, and a reply whose stated version is newer
than the viewer.

- a. Refuse the whole reply and carry out none of its commands.
- b. Skip the unknown command and carry out the rest, with a visible note that something was left out.
- c. A command may carry a fallback, which is an older command to carry out in its place.

Cost: (a) is the safest and means every vocabulary change breaks old viewers. (b) can change the meaning of what
is displayed by leaving a part out, and is more dangerous for a behaviour command than for a display command. (c)
puts the cost on authors.

Recommendation: (a) for a reply that holds an unknown behaviour command or a newer major version. For an unknown
display command, (c) where the author gave a fallback and otherwise (b).

### BQ-7. How does one large thing arrive?

By ruling R2 a render is not bounded by the frame size, because it can be built from several requests. What is
left is a single thing that cannot be split into commands, such as an image, when it is larger than one frame
(131072 bytes).

- a. Such things are not allowed: an image must fit in one reply.
- b. A request for a part: the viewer asks for a stated range of a named object and repeats until it is complete.
- c. A higher frame limit for these requests.

Cost: (a) needs nothing new and limits images severely. (b) is a new rule for the vocabulary and for the bridge's
scoring, since one image becomes many requests (fact 5). (c) changes a bound the nodes rely on to limit memory.

Recommendation: (b), decided together with BQ-12, because both are about how many requests a render costs.

### BQ-8. Which behaviours can a command trigger?

By ruling R1 a command may trigger behaviour in the viewer, and by ruling R3 a behaviour is something the viewer
already has, chosen by data. The question is the closed list. Candidates:

- a. Send a request for commands and carry out the reply (this is what makes ruling R2 work).
- b. Go to an address: clear the display and start a new render from that address.
- c. Send a request with no reply (a `cast`).
- d. Send a request again after a stated time (see BQ-10).
- e. Keep a named value in the viewer and send it back with later requests, so that the node need not remember
  each reader.
- f. Things on the reader's machine: copy text, save a file, open another application, show a notification.

Sub-question: which of these may happen without the person acting? A reply that makes the viewer send requests by
itself is needed for (a), and it also lets a reply make the viewer send many requests.

Cost: (a) to (d) need nothing new in the protocol. (e) is the equivalent of a cookie, with the same privacy
questions. (f) is where a command can harm its reader, so each item needs its own rule and the reader's consent.
Automatic requests need a bound, or one reply can spend the reader's whole allowance at the bridge (fact 5).

Recommendation: (a), (b), (c) and (d) in the first version, with a stated maximum number of automatic requests for
one render. (e) only with a ruling on privacy. From (f), only copying text, and only when the person acts.

### BQ-9. How does a form send what the reader typed?

- a. The submit action names a request, and the viewer adds one map argument that holds each field's name and
  value.
- b. The submit action names a request and says, for each argument position, which field supplies it.

Cost: (a) is uniform and every function that takes a form has the same shape. (b) lets a form call existing
functions unchanged and makes the command more complicated.

Recommendation: (a). The values are byte strings, numbers and booleans only, and the function checks them: what
arrives from a viewer is untrusted input like anything else from the network.

### BQ-10. Can the display change without the reader acting?

The node sends nothing a client did not ask for (fact 8).

- a. No. The display changes only when the reader acts.
- b. A command may tell the viewer to send a stated request again after a stated time (BQ-8 d).
- c. A new subscription: the viewer stays connected and the node sends changes.

Cost: (b) needs nothing new and costs a request per refresh per reader, which the bridge's limits will count (fact
5). (c) is a new kind of connection with its own limits, and it changes fact 2.

Recommendation: (b), with a lowest allowed interval that the viewer enforces. Leave (c) until there is a use that
needs it.

### BQ-11. Is accessibility part of the vocabulary?

- a. Yes: an image must have a text alternative, a form field must have a label, a render must state its language,
  and a viewer refuses or marks a command that lacks them.
- b. They are allowed and optional.

Cost: (a) costs authors a little on every reply and cannot be added later without breaking what authors wrote.

Recommendation: (a). This is cheap now and very expensive to add afterwards.

### BQ-20. How do the commands of several requests become one render?

Ruling R2 allows several requests for one render. The replies may arrive in any order, and some may not arrive.

- a. Strictly in sequence: the viewer sends the next request only after carrying out the previous reply.
- b. In parallel, with named regions: each request is tied to a region, and its reply's commands apply only inside
  that region, so the order of arrival does not matter.
- c. In parallel with no restriction: commands apply as they arrive.

Cost: (a) is simple and slow, since each request is a new connection today (fact 2). (b) needs the rule that a
reply cannot touch anything outside its region, which also limits what a faulty or hostile reply can do. (c) makes
the result depend on timing.

Recommendation: (b).

### BQ-21. What does the viewer show while a render is incomplete, and when part of it fails?

- a. Nothing until every request has been answered.
- b. Each region as it arrives, with a visible mark on a region that is still waiting or that failed.

Sub-question: is a failed region tried again, and how many times? A refusal looks the same as a failure (fact 3),
and repeated requests raise the reader's score at the bridge (fact 5).

Recommendation: (b), with no automatic retry of a failed region. The person may ask again.

### BQ-22. What state does the viewer keep, and when is it thrown away?

Commands act on a display the viewer holds. The questions are what a command may refer to (regions by name; fields
by name; values kept under BQ-8 e), how long each lasts (until the next address is visited; until the viewer
closes; longer), and whether commands from one network can ever see or change the state made by another.

Recommendation: the display and its regions last until the viewer goes to another address. State is separate for
each network, with no exception.

## 6. Open questions: addressing

### BQ-12. What does the viewer connect to?

- a. A bridge, with the existing `call`. The viewer is an edge peer and the commands come from a TRUST function
  behind the bridge.
- b. A TRUST node directly. The viewer is a TRUST client and needs a TRUST implementation in its language, which
  does not exist yet.
- c. A new node role made for serving commands.

Cost: (a) works with what exists and has facts 1 to 5 of section 3. Fact 2 weighs more now that one render may
take several requests (ruling R2): each is a new connection, handshake and admission. (b) may allow many requests on one connection (TRUST has
sessions) and removes TEMPUS admission from the picture, so the reader's identity must be listed at each TRUST node.
(c) is new design work in the node.

Recommendation: (a) for a first version, because it needs no change. Rule at the same time on whether a bridge may
keep a connection open for more than one call from the same admitted peer. With ruling R2 that change is no longer
a refinement: it decides whether a render of several requests is quick or slow, and how the bridge's per-peer
limits (fact 5) should count them.

### BQ-13. What are the parts of an address?

An address must let the viewer find a node to ask and tell it what to ask for. Candidate parts:

- the network: which TEMPUS network this is, which decides the token and the producer key the viewer uses;
- the place: either "any bridge of this network" or one bridge named by its identity;
- the request: module, function and arguments;
- optionally a region of the render to show first.

Sub-questions:

- a. Does an address name a network by a name a person chose, by the producer's public key, or by both?
- b. May an address name one node, or only a network? Gossip exists so that a client need not know a fixed node, and
  an address that names one node is dead when that node is.
- c. Are the module and function named as they are in the code, or does the application publish names that it maps to
  functions? The second hides the code's structure and lets it change.

Recommendation: a network named by the producer's key with an optional readable label; "any bridge" as the normal
case; published names mapped by the application, not raw module and function names. An address names the first request
of a render; the further requests come from commands (BQ-8 a) and need no text form.

### BQ-14. What is the text form of an address?

- a. A URI with its own scheme, for example `tempus://<network>/<name>?<arguments>`, so that the machine can hand
  such links to the viewer and existing software treats it as a link.
- b. A form that is not a URI, such as an ETF term printed as text.

Cost: (a) must fit arbitrary terms into text, which needs an encoding rule for arguments. (b) is exact and nobody
can type it or paste it into a message safely.

Recommendation: (a). Arguments are limited to byte strings, integers and booleans in the text form, which matches
BQ-9. The scheme name is the owner's to choose.

### BQ-15. How does the viewer find its first node?

A TEMPUS peer joins through a sentinel whose address it must already have.

- a. The address carries a sentinel's host and port.
- b. The viewer is given a list of networks, each with its sentinels and producer key, by the person or by an
  installer.
- c. A directory network that the viewer always knows, which answers "where is network X".

Cost: (a) makes addresses long and ties them to one machine. (b) means a link to an unknown network cannot be
followed until the person adds the network. (c) is a central service, with the trust questions that brings.

Recommendation: (b) first, with a clear screen for adding a network from a file or a code. Decide (c) later.

### BQ-16. How does a reader know whose commands the viewer is carrying out?

On the web a domain name and a certificate authority answer this. Here identity is a key and a token.

- a. Show the network's label and the fingerprint of its producer key, and nothing more.
- b. Networks the person has added carry a name the person chose; the viewer shows that name beside what
  they display.
- c. A naming service that binds readable names to producer keys.

Cost: (a) is honest and unreadable. (b) is the model of a contact list. (c) is a new authority.

Recommendation: (b). Also decide whether the viewer shows which bridge answered, since any bridge of the network may, and
since the requests of one render may be answered by different bridges.

### BQ-17. What identity does the viewer present, and what does a node learn about the reader?

The viewer needs an Ed25519 key and a token for it from the network's producer.

- a. One key for the viewer, used on every network.
- b. One key per network.
- c. One key per network and per visit.

Sub-question: how does a viewer get a token? Today a producer issues tokens by a process outside the protocol. A
public network would need a way to issue a token to a viewer it has never seen, and a rule for when to refuse.

Cost: (a) lets networks that compare notes recognise the same reader. (c) makes scoring by peer meaningless, since
every visit is a new peer. Issuing tokens to anyone weakens what admission means.

Recommendation: (b). The token question needs its own ruling before any public use.

### BQ-18. May the viewer keep a reply and use it again without asking?

- a. Never.
- b. For as long as a command in the reply says it may be kept.
- c. For as long as it says, and it may be used when no node can be reached, with the display marked as old.

Sub-question: only display commands can sensibly be kept. Carrying out a kept behaviour command again would repeat
a request the node did not expect.

Recommendation: (c) for replies that hold display commands only. The time is stated in seconds; with no statement
nothing is kept.

### BQ-19. What does the reader see when a reply does not come?

A refusal, a failed function and a timeout look the same to the client (fact 3).

- a. Accept that: one message, "this could not be fetched", shown in the region that was waiting (BQ-21).
- b. Change the bridge to send a reason to an admitted peer.

Cost: (b) tells a hostile peer why it was refused, which the current design avoids on purpose.

Recommendation: (a) for refusals. For a function that ran and wants to report a problem, the function returns commands
that display the problem, which are ordinary commands. That needs no protocol change.

## 7. Risks to keep in view

- A reply is untrusted input. The viewer must check every command against the vocabulary before carrying it out,
  with bounds on depth, command count and text length, as the nodes check frames. Because no reply holds code
  (ruling R3), checking the data is the whole of the defence.
- A request is made with the reader's identity. A reply from one place that causes a request to another place is
  the same danger as on the web. The simplest rule is that a command may name requests only on its own network.
- The bridge's per-peer limits were designed for programs, not for people clicking. They may need values chosen for
  this use, and the viewer must slow down by itself when it is refused.
- Every viewer must agree on the vocabulary. A reference set of replies with their expected result, used as a trial
  by every implementation, is the same method BEES uses for its frames.

## 8. Suggested order of rulings

1. BQ-12 (what the viewer connects to) and BQ-8 (which behaviours exist). BQ-1 is ruled. Everything else depends
   on these.
2. BQ-2, BQ-3, BQ-4, BQ-5 and BQ-6: the vocabulary's form; BQ-20, BQ-21 and BQ-22: how replies become a render.
3. BQ-13 and BQ-14: the address.
4. BQ-17 and BQ-15: identity and the first node. These decide whether a public network is possible at all.
5. The rest.

After the first two groups are ruled, a small trial is possible with no new protocol work: one bridge, one
exported function that returns a list of commands, and a command-line program built on an existing extension that
sends the request, checks the commands and prints what it would display and do.
