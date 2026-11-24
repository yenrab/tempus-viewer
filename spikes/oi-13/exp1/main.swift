import Foundation



print("swift: main thread starts, isMain=\(Thread.isMainThread)")
let t = Thread {
    print("swift: silica thread starts, isMain=\(Thread.isMainThread)")
    let rc = call_silica()
    print("swift: silica main returned \(rc)")
}
t.start()
Thread.sleep(forTimeInterval: 2.0)
print("swift: main thread still alive after 2 s")
