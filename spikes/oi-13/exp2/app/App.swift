import SwiftUI
import Foundation

@MainActor
final class Model: ObservableObject {
    @Published var label = "no events yet"
    @Published var clicks = 0
    var latencies: [Double] = []
    var autoTarget = 0
    var lastN = 0
    var outOfOrder = 0

    func click() {
        clicks += 1
        sendEvent(n: clicks)
    }

    func sendEvent(n: Int) {
        let t0 = DispatchTime.now().uptimeNanoseconds
        let text = "click \(n) \(t0)"
        Array(text.utf8).withUnsafeBufferPointer { viewer_host_push_event($0.baseAddress, UInt64($0.count)) }
    }

    func receive(_ text: String) {
        // text: "click N t0"; the update below happens on the main thread
        let parts = text.split(separator: " ")
        if parts.count == 3, let t0 = UInt64(parts[2]) {
            let dt = Double(DispatchTime.now().uptimeNanoseconds - t0) / 1e6
            latencies.append(dt)
            if let n = Int(parts[1]) { if n <= lastN { outOfOrder += 1 }; lastN = n }
            label = "Silica answered click \(parts[1]) in \(String(format: "%.3f", dt)) ms"
        } else {
            label = text
        }
        if autoTarget > 0 && latencies.count >= autoTarget { finishAuto() }
    }

    func finishAuto() {
        let s = latencies.sorted()
        let mean = s.reduce(0, +) / Double(s.count)
        print("auto: out of order \(outOfOrder)")
        print(String(format: "auto: %d round trips, min %.3f ms, median %.3f ms, mean %.3f ms, max %.3f ms",
                     s.count, s.first!, s[s.count / 2], mean, s.last!))
        fflush(stdout)
        exit(0)
    }
}

@MainActor let model = Model()

@main
struct SpikeApp: App {
    init() {
        // The Silica runtime runs on its own thread; the main thread stays with SwiftUI.
        viewer_host_set_handler { p, n in
            let text = String(decoding: UnsafeBufferPointer(start: p, count: Int(n)), as: UTF8.self)
            let onMain = Thread.isMainThread
            if onMain { print("handler unexpectedly on the main thread") }
            DispatchQueue.main.async { MainActor.assumeIsolated { model.receive(text) } }
        }
        let t = Thread { _ = viewer_host_start_silica() }
        t.stackSize = 16 << 20
        t.name = "silica-main"
        t.start()
        if CommandLine.arguments.contains("--crash") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { raise(SIGSEGV) }
        }
        if let i = CommandLine.arguments.firstIndex(of: "--auto"), i + 1 < CommandLine.arguments.count,
           let n = Int(CommandLine.arguments[i + 1]) {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                MainActor.assumeIsolated {
                    model.autoTarget = n
                    for k in 1...n {
                        DispatchQueue.main.asyncAfter(deadline: .now() + (CommandLine.arguments.contains("--burst") ? 0 : Double(k) * 0.01)) {
                            MainActor.assumeIsolated { model.sendEvent(n: k) }
                        }
                    }
                }
            }
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(model)
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var m: Model
    var body: some View {
        VStack(spacing: 16) {
            Text(m.label).font(.title3)
            Button("Click (event goes to Silica and back)") { m.click() }
        }
        .padding(40)
        .frame(minWidth: 480, minHeight: 200)
    }
}
