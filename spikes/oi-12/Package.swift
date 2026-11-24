// swift-tools-version:5.9
// OI-12 spike: an Ed25519 key held in the macOS Keychain, used as the TEMPUS client identity.
// The BEES Swift client library is used in place (a path dependency), not copied. This needs the BEES checkout to be
// a sibling of this repository: ../project-bees
import PackageDescription

let package = Package(
    name: "keychain-spike",
    platforms: [.macOS("26.0")],
    dependencies: [
        .package(path: "../../../project-bees/example_tempus_clients/swift"),
    ],
    targets: [
        .executableTarget(name: "keychain-spike",
                          dependencies: [.product(name: "TempusClient", package: "swift")],
                          path: "Sources/keychain-spike"),
    ]
)
