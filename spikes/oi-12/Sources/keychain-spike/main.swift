import Foundation
import Security
import CryptoKit
import TempusClient

// ---- Keychain: a 32-byte Ed25519 seed as a generic password item -------------------------------------------------
let service = "org.tempus.viewer.spike"
let account = "network-\(UUID().uuidString)"

func base(_ account: String) -> [String: Any] {
    [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
}
func store(_ seed: Data, account: String, dataProtection: Bool) -> OSStatus {
    var q = base(account)
    q[kSecValueData as String] = seed
    q[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
    q[kSecAttrSynchronizable as String] = false
    if dataProtection { q[kSecUseDataProtectionKeychain as String] = true }
    return SecItemAdd(q as CFDictionary, nil)
}
func load(account: String) -> (OSStatus, Data?) {
    var q = base(account)
    q[kSecReturnData as String] = true
    q[kSecMatchLimit as String] = kSecMatchLimitOne
    var out: CFTypeRef?
    let s = SecItemCopyMatching(q as CFDictionary, &out)
    return (s, out as? Data)
}
func remove(account: String) -> OSStatus { SecItemDelete(base(account) as CFDictionary) }

var failures = 0
func check(_ what: String, _ ok: Bool, _ extra: String = "") {
    print("\(ok ? "PASS" : "FAIL")  \(what)\(extra.isEmpty ? "" : "  (\(extra))")")
    if !ok { failures += 1 }
}
func hex(_ b: [UInt8]) -> String { b.prefix(4).map { String(format: "%02x", $0) }.joined() + "..." }

// 1. does the system keep a seed, and give back exactly the same bytes?
var seedBytes = [UInt8](repeating: 0, count: 32)
check("random seed", SecRandomCopyBytes(kSecRandomDefault, 32, &seedBytes) == errSecSuccess)
let seed = Data(seedBytes)

let dp = store(seed, account: account + "-dp", dataProtection: true)
print("INFO  data-protection keychain add: status \(dp) (\(SecCopyErrorMessageString(dp, nil) as String? ?? "?"))")
let st = store(seed, account: account, dataProtection: false)
check("add to the login keychain", st == errSecSuccess, "status \(st)")
let (rs, back) = load(account: account)
check("read it back", rs == errSecSuccess && back == seed, "status \(rs)")
let dup = store(seed, account: account, dataProtection: false)
check("a second add of the same item is refused", dup == errSecDuplicateItem, "status \(dup)")

// 2. the same seed in CryptoKit and in the BEES library's OpenSSL give one key
let ck = try! Curve25519.Signing.PrivateKey(rawRepresentation: back ?? seed)
let sk = try! SigningKey(seed: [UInt8](back ?? seed))
check("public key: CryptoKit == OpenSSL (TempusClient)", Array(ck.publicKey.rawRepresentation) == sk.pub, hex(sk.pub))
let msg = Array("hello viewer".utf8)
let sigOpenSSL = try! sk.sign(msg)
check("CryptoKit verifies an OpenSSL signature", ck.publicKey.isValidSignature(Data(sigOpenSSL), for: Data(msg)))
let sigCK = Array(try! ck.signature(for: Data(msg)))
check("OpenSSL verifies a CryptoKit signature", ed25519Verify(pub: sk.pub, message: msg, sig: sigCK))

// 3. the library's identity from the stored seed: certificate and what tempus/1 requires of it
let nowSec = Int64(Date().timeIntervalSince1970)
let producer = try! SigningKey(seed: (0..<32).map { UInt8($0) })      // TEST ONLY producer (seed 00..1f)
func testToken(sub: [UInt8], typ: String) -> [UInt8] {
    let payload = try! tokenPayload(kid: Array("k1".utf8), sub: sub, typ: typ, nbf: nowSec - 100, exp: nowSec + 3600)
    return try! producer.sign(payload) + payload
}
let me = try! Identity(seed: [UInt8](back ?? seed), token: testToken(sub: sk.pub, typ: "tempus_edge"), addr: "127.0.0.1:1")
check("certificate key == the stored key", (try? certificateKey(der: me.certDER)) == sk.pub)

// 4. a real TLS 1.3 handshake and admission, with the Keychain-held key as the client identity
let bridgeSeed = (0..<32).map { UInt8(100 + $0) }
let bridgeKey = try! SigningKey(seed: bridgeSeed)
let bridge = try! Identity(seed: bridgeSeed, token: testToken(sub: bridgeKey.pub, typ: "tempus_bridge"), addr: "127.0.0.1:1")
func verifier(whitelist: Set<[UInt8]>?) -> Verifier {
    Verifier(producerPub: producer.pub, kid: Array("k1".utf8), clock: { Int64(Date().timeIntervalSince1970) }, skew: 60,
             types: peerTypes, whitelist: whitelist)
}
var served = 0
let listener = try! Listener(identity: bridge, verifier: verifier(whitelist: nil), timeout: 5.0) { _ in
    served += 1
    return .reply(try! sampleReply(store: "tempus_edge", entries: []))
}.start()
let outcome = dial(listener.address, identity: me, verifier: verifier(whitelist: [sha512(bridge.certDER)]),
                   request: try! sample(store: "tempus_edge", n: 1), timeout: 5.0)
check("handshake, admission and one request, client key from the Keychain", outcome.what == "reply",
      "dialer saw: \(outcome.line)")
check("the listener served the request", served == 1)

// 5. a different seed (not the one admitted) is refused: the pass is bound to the key
var other = [UInt8](repeating: 0, count: 32); _ = SecRandomCopyBytes(kSecRandomDefault, 32, &other)
let otherKey = try! SigningKey(seed: other)
let wrong = try! Identity(seed: other, token: testToken(sub: sk.pub, typ: "tempus_edge"), addr: "127.0.0.1:1")
let refused = dial(listener.address, identity: wrong, verifier: verifier(whitelist: [sha512(bridge.certDER)]),
                   request: try! sample(store: "tempus_edge", n: 1), timeout: 5.0)
check("a key that does not match the pass is refused", refused.what != "reply", "dialer saw: \(refused.line)")
_ = otherKey

// 6. cleanup, and what remains
check("delete the item", remove(account: account) == errSecSuccess)
_ = remove(account: account + "-dp")
let (gone, _) = load(account: account)
check("it is gone", gone == errSecItemNotFound, "status \(gone)")
print(failures == 0 ? "ALL PASS" : "\(failures) FAILED")
exit(failures == 0 ? 0 : 1)
