"""A small External Term Format writer and reader, written from the format description (erts, external term format).
Independent of Silica and of Swift on purpose: the reference replies are checked against Silica's encoder byte for byte.

Map keys are written in alphabetical order, which is the order Silica's encoder uses, so that bytes match.
Terms: Atom(name), tuples (Python tuple), lists (Python list), binaries (bytes), integers, maps (Python dict, key order kept).
Text given as str is written as a binary (UTF-8), which is how BEES carries strings."""
import struct


class Atom(str):
    pass


def enc(t):
    return b"\x83" + _enc(t)


def _enc(t):
    if isinstance(t, Atom):
        b = t.encode("utf-8")
        assert len(b) < 256
        return bytes([119, len(b)]) + b                      # SMALL_ATOM_UTF8_EXT
    if isinstance(t, bool):
        return _enc(Atom("true" if t else "false"))
    if isinstance(t, int):
        if 0 <= t < 256:
            return bytes([97, t])                            # SMALL_INTEGER_EXT
        if -2**31 <= t < 2**31:
            return b"b" + struct.pack(">i", t)               # INTEGER_EXT
        mag = abs(t)
        digits = mag.to_bytes((mag.bit_length() + 7) // 8, "little")
        return bytes([110, len(digits), 1 if t < 0 else 0]) + digits   # SMALL_BIG_EXT
    if isinstance(t, str):
        return _enc(t.encode("utf-8"))
    if isinstance(t, (bytes, bytearray)):
        return b"m" + struct.pack(">I", len(t)) + bytes(t)   # BINARY_EXT
    if isinstance(t, tuple):
        assert len(t) < 256
        return bytes([104, len(t)]) + b"".join(_enc(x) for x in t)   # SMALL_TUPLE_EXT
    if isinstance(t, list):
        if not t:
            return b"j"                                      # NIL_EXT
        return b"l" + struct.pack(">I", len(t)) + b"".join(_enc(x) for x in t) + b"j"
    if isinstance(t, dict):
        return b"t" + struct.pack(">I", len(t)) + b"".join(_enc(Atom(k)) + _enc(v) for k, v in sorted(t.items()))   # keys in alphabetical order, as Silica writes them
    raise TypeError(f"cannot encode {type(t)}")


def dec(b):
    assert b[0] == 131
    t, n = _dec(b, 1)
    assert n == len(b), "trailing bytes"
    return t


def _dec(b, i):
    tag = b[i]
    i += 1
    if tag == 97:
        return b[i], i + 1
    if tag == 98:
        return struct.unpack(">i", b[i:i + 4])[0], i + 4
    if tag == 110:
        n, sign = b[i], b[i + 1]
        v = int.from_bytes(b[i + 2:i + 2 + n], "little")
        return (-v if sign else v), i + 2 + n
    if tag in (119, 100):                                    # SMALL_ATOM_UTF8_EXT; ATOM_EXT (latin-1, 2-byte length)
        if tag == 119:
            n = b[i]; i += 1
        else:
            n = struct.unpack(">H", b[i:i + 2])[0]; i += 2
        return Atom(b[i:i + n].decode("utf-8")), i + n
    if tag == 109:
        n = struct.unpack(">I", b[i:i + 4])[0]
        return bytes(b[i + 4:i + 4 + n]), i + 4 + n
    if tag == 104:
        n = b[i]; i += 1
        out = []
        for _ in range(n):
            x, i = _dec(b, i); out.append(x)
        return tuple(out), i
    if tag == 106:
        return [], i
    if tag == 107:                                           # STRING_EXT: a list of bytes (Erlang writes it for small integers)
        n = struct.unpack(">H", b[i:i + 2])[0]
        return list(b[i + 2:i + 2 + n]), i + 2 + n
    if tag == 108:
        n = struct.unpack(">I", b[i:i + 4])[0]; i += 4
        out = []
        for _ in range(n):
            x, i = _dec(b, i); out.append(x)
        assert b[i] == 106, "improper list"
        return out, i + 1
    if tag == 116:
        n = struct.unpack(">I", b[i:i + 4])[0]; i += 4
        out = {}
        for _ in range(n):
            k, i = _dec(b, i); v, i = _dec(b, i)
            out[str(k)] = v
        return out, i
    raise ValueError(f"unsupported ETF tag {tag}")


def show(t, indent=0):
    """Readable text in the style of Erlang's io:format ~p, for the .txt listings."""
    pad = "  " * indent
    if isinstance(t, Atom):
        return str(t)
    if isinstance(t, bool):
        return "true" if t else "false"
    if isinstance(t, int):
        return str(t)
    if isinstance(t, (bytes, str)):
        s = t if isinstance(t, str) else t.decode("utf-8", "replace")
        return '<<"' + s.replace('"', '\\"') + '">>' if len(s) <= 72 else f'<<"{s[:60]}..." ({len(t)} bytes)>>'
    if isinstance(t, tuple):
        return "{" + ", ".join(show(x, indent) for x in t) + "}"
    if isinstance(t, list):
        if not t:
            return "[]"
        flat = "[" + ", ".join(show(x, indent) for x in t) + "]"
        if len(flat) <= 100:
            return flat
        return "[\n" + ",\n".join(pad + "  " + show(x, indent + 1) for x in t) + "\n" + pad + "]"
    if isinstance(t, dict):
        return "#{" + ", ".join(f"{k} => {show(v, indent)}" for k, v in t.items()) + "}"
    raise TypeError(type(t))
