# OI-12 spike: an Ed25519 key in the macOS Keychain as the TEMPUS client identity

Question (requirements OI-12): can an Ed25519 key be held in the macOS Keychain in a form that the BEES Swift client
library's OpenSSL client certificate can use?

Answer: yes, as a 32-byte seed kept in a generic password item. Run 2026-11-24 on macOS 26, Swift 6.3.3, OpenSSL 4.1.0.

## Run it

The BEES checkout must be a sibling of this repository (`../project-bees`); the library is used in place through a
path dependency and is not copied.

    P=/opt/homebrew/opt/openssl
    swift build --disable-sandbox -Xcc -I$P/include -Xlinker -L$P/lib
    .build/debug/keychain-spike

## What was shown (13 checks, all pass)

- A random 32-byte seed is added to the login keychain as a generic password item
  (`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`, not synchronised), read back byte for byte, a duplicate add is
  refused, and delete leaves nothing behind.
- The same seed gives one key in CryptoKit and in the library's OpenSSL: equal public keys, and each side verifies the
  other's signature.
- `Identity(seed:token:addr:)` builds the self-signed certificate from that seed, and `certificateKey(der:)` returns the
  stored key.
- A real TLS 1.3 handshake and admission over loopback: a `Listener` playing a bridge, and `dial` using the
  Keychain-held key as the client identity. The dialer got a reply. A key that does not match the pass is closed at the
  challenge step.

## Findings

- Security.framework has no Ed25519 key type (its headers do not mention it), so the key cannot be a Keychain key
  object. It is a secret kept as an item and passed to OpenSSL as raw bytes, as the library already expects. The secret
  is in process memory while it is in use. As far as I know the Secure Enclave holds only P-256 keys; that was not tested.
- The data-protection keychain refused the add with -34018 ("a required entitlement isn't present"): this build is not
  signed with an entitlement. The login (file-based) keychain worked. A signed app with a keychain access group can
  choose the data-protection keychain. Which one the viewer uses is to be decided with the signing plan.
- Not tested: reading an item from a rebuilt or differently signed binary (the file-based keychain ties access to the
  code identity and may prompt), and the Keychain being locked.
- The library's `dial` needs the dialer's identity to carry an advertised `host:port` even though a viewer does not
  listen. The spike passes `127.0.0.1:1`. The viewer must do the same, or the library must change.
- A test pass for the viewer's own key can be made with the library's public calls (`tokenPayload` and
  `SigningKey.sign` with the fixed test producer seed). The spike does this. So the viewer's test mode need not load a
  fixed test key (requirement 4.9): a test-only tool can sign a pass for the key the viewer made.
