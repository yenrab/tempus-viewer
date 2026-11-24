"""Command vocabulary v0, PROVISIONAL (testnet only). Each command is a tagged tuple carrying one map: {Tag, #{...}}.

Why a tagged tuple and not a bare map: the Silica encoder allows only one record variant in a sum, so a mixed list
of commands cannot be a list of maps in Silica (spike: testnet/experiments/etf-commands, error E2404). Map keys are
written in alphabetical order (what Silica does). Text is a binary. Request arguments are lists of binaries, because
a TRUST export takes `args <ElemType>`, one element type for the whole list.
"""
from etf import Atom as A

VERSION = 1


def cmd(_name, **m):
    return (A(_name), m)


def vocabulary(): return cmd("vocabulary", version=VERSION)
def title(text): return cmd("title", text=text)
def language(tag): return cmd("language", tag=tag)
def keep(seconds): return cmd("keep", seconds=seconds)

def region(into, name): return cmd("region", into=into, name=name)
def clear(r): return cmd("clear", region=r)
def remove(r): return cmd("remove", region=r)

def heading(into, level, text): return cmd("heading", into=into, level=level, text=text)
def paragraph(into, *runs): return cmd("paragraph", into=into, runs=[plain(r) if isinstance(r, str) else r for r in runs])
def listing(into, items, ordered=False):
    return cmd("list", into=into, ordered=ordered, items=[[plain(r) if isinstance(r, str) else r for r in
                                                           (it if isinstance(it, list) else [it])] for it in items])
def quotation(into, text, cite=""): return cmd("quotation", into=into, runs=[plain(text)], cite=cite)
def preformatted(into, text): return cmd("preformatted", into=into, text=text)
def rule(into): return cmd("rule", into=into)

def plain(t): return (A("plain"), t)
def emph(t): return (A("emph"), t)
def strong(t): return (A("strong"), t)
def code(t): return (A("code"), t)
def link(text, to): return (A("link"), {"text": text, "to": to})

def request(name, *args): return {"name": name, "args": list(args)}
def block_link(into, text, to): return cmd("link_block", into=into, text=text, to=to)
def button(into, label, name, *args): return cmd("button", into=into, label=label, request=request(name, *args))

def field_text(name, label, value=""): return (A("text"), {"name": name, "label": label, "value": value})
def field_choice(name, label, options, value=""):
    return (A("choice"), {"name": name, "label": label, "value": value,
                          "options": [{"value": v, "label": l} for v, l in options]})
def field_tick(name, label, value=False): return (A("tick"), {"name": name, "label": label, "value": value})
def form(into, name, fields, submit_label, submit_name):
    return cmd("form", into=into, name=name, fields=fields, submit=request(submit_name), label=submit_label)

def image(into, ident, alt, width, height, size):
    return cmd("image", into=into, id=ident, alt=alt, width=width, height=height, bytes=size)
def table(into, caption, columns, rows): return cmd("table", into=into, caption=caption, columns=columns, rows=rows)
def table_rows(r, rows): return cmd("table_rows", region=r, rows=rows)

def fetch(into, name, *args): return cmd("fetch", into=into, request=request(name, *args))
def goto(to): return cmd("goto", to=to)
def refresh(into, every_s, name, *args): return cmd("refresh", into=into, every_s=every_s, request=request(name, *args))
