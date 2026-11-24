# TEMPUS viewer

A TEMPUS viewer is a native application that a person uses to visit places on TEMPUS networks. It is what a web
browser is to the web, with one large difference: it does not speak HTTP and it does not receive pages. This
repository holds the design and requirements for one implementation of a viewer, for macOS.

Status: design and requirements only. Nothing is built yet.

## What a viewer is

TEMPUS is the part of SEMP for nodes that come and go. A viewer is an ordinary peer of such a network. It follows these
rules:

- **It asks a node for commands.** The person gives an address of the form `tempus://host/name?arguments`. The
  viewer sends the request that the address names to the bridge at that host. The bridge answers with one term, a
  list of commands.
- **A command is data, never code.** A command says to show a heading, add an item to a list, fill a table, show an
  image, or send another request. It selects something the viewer already knows how to do. A reply holds no script,
  expression, condition or loop. All logic runs on the nodes. The viewer checks every command against a fixed
  vocabulary and refuses what it does not know.
- **The viewer decides how things look.** A command says what a thing is. The viewer shows it with the controls of the
  machine it runs on, so every network is usable with a keyboard, a screen reader, dark mode and the person's text
  size, with no extra work by the author.
- **A screen can be built from several requests.** A reply may name further requests that fill named regions, so the
  size of one message does not limit what can be shown.
- **Identity is a key and a pass, not a domain and a certificate authority.** A person adds a network by importing a
  file, the viewer makes a key for that network and keeps it in the Keychain, and the network's owner issues a pass for
  that key.
- **Only `tempus://` links exist.** The host is a domain name or an IP address and names one bridge.

## What this implementation is for

This is a viewer for macOS, with a SwiftUI window and a Silica core: a root supervisor, a tree of actors that each have
one job, and `cast` in preference to `call`. A small Swift host owns the window and reaches the Silica program through
FFI.

It has two purposes.

1. **To be a viewer.** A general tool for visiting TEMPUS networks, with tabs, history, tables, images, forms, an
   address bar and a list of the networks the person has added.
2. **To exercise the node code of [Project BEES](https://github.com/Silica-Language-and-Compiler/project-bees).** The viewer is a demanding, real client of what
   BEES builds. Running it against a test network (one bridge, several TRUST nodes and several TEMPUS nodes, built
   with the Silica compiler) uses the bridge, admission, the TRUST call path, the node's limits and scoring, and the
   Swift TEMPUS client library as a person would, and it shows where they fall short. Defects found in the Swift client
   are fixed in BEES, in place. Things the viewer needs that BEES lacks, such as arguments of more than one type in a
   `call` and a way to learn a request's mark before sending it, are reported and built there.

The viewer's own conformance set, a fixed collection of valid and invalid replies with their expected results, is also
a test of any node or server that builds replies.

## Documents

- [TEMPUS-viewer-requirements.md](TEMPUS-viewer-requirements.md): what the viewer must do, as ruled by the owner, with
  the open items listed apart from the requirements. Start here.
- [TEMPUS-viewer-design.md](TEMPUS-viewer-design.md): the first design notes. Each question is numbered BQ-n, with the
  options considered, their costs and a recommendation.

## What is needed to build it

The compiler binaries from the [releases of the Silica repository](https://github.com/Silica-Language-and-Compiler/silica/releases)
(the latest release), the Swift toolchain,
and OpenSSL 4.1.0 or later, as [BEES's requirements page](https://github.com/Silica-Language-and-Compiler/project-bees/blob/main/contract/what-is-required-to-use.md) requires.

## Where it is going

The first steps are two spikes and a measurement:

1. A SwiftUI application that owns the main thread while the Silica runtime runs beside it, with a click arriving as
   a cast to an actor.
2. A key held in the macOS Keychain that the TLS client certificate can use.
3. A command-line program that sends a request to a test bridge, checks the commands and prints what it would show,
   and measures how long requests take.
