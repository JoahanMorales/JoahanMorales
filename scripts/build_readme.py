#!/usr/bin/env python3
"""Rebuild the generated parts of README.md from data/profile.json.

    python3 scripts/build_readme.py          # rewrite README.md
    python3 scripts/build_readme.py --check  # exit 1 if README.md is out of date

A new hackathon or tool is one entry in data/profile.json; the GitHub Action runs this on every push that changes it.
Generated blocks live between <!-- NAME:start --> and <!-- NAME:end --> markers; nothing else is touched.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
VIOLET, VIOLET_SOFT, INK = "7c3aed", "c4b5fd", "1a1625"
COLS = 4


def badge(left, right, color):
    esc = lambda s: quote(s.replace("-", "--").replace("_", "__").replace(" ", "_"), safe="_")
    return ("https://img.shields.io/badge/%s-%s-%s?style=flat-square&labelColor=%s"
            % (esc(left), esc(right), color, INK))


def card(h):
    color = VIOLET if h.get("first") else VIOLET_SOFT
    name = '<a href="%s"><b>%s</b></a>' % (h["url"], h["project"]) if h.get("url") else "<b>%s</b>" % h["project"]
    kit = " ◆" if h.get("kit") else ""
    return ('<td width="25%%" valign="top">\n'
            '<img src="%s" alt="%s · %s"><br>\n'
            '<sub>%s · %s</sub>\n'
            '<h4>%s%s</h4>\n'
            '%s\n'
            '</td>') % (badge(h["date"], h["award"], color), h["award"], h["date"], h["event"], h["place"], name, kit,
                        h["pitch"])


def next_card(n):
    return ('<td width="25%%" valign="top">\n'
            '<img src="%s" alt="siguiente"><br>\n'
            '<sub>&nbsp;</sub>\n'
            '<h4>%s</h4>\n'
            '<a href="%s">%s</a>\n'
            '</td>') % (badge("2027", "?", "2a2438"), n["title"], n["url"], n["text"])


def hackathons(data):
    cells = [card(h) for h in data["hackathons"]]
    if data.get("next"):
        cells.append(next_card(data["next"]))
    rows = ["<tr>\n%s\n</tr>" % "\n".join(cells[i:i + COLS]) for i in range(0, len(cells), COLS)]
    firsts = sum(1 for h in data["hackathons"] if h.get("first"))
    head = "**%d premios**, %d de ellos primer lugar." % (len(data["hackathons"]), firsts)
    foot = "<sub>◆ hecho con UPIIXIA Agentic Kit</sub>"
    return "%s\n\n<table>\n%s\n</table>\n\n%s" % (head, "\n".join(rows), foot)


def icon(slug):
    if slug.startswith("@"):
        return "assets/icons/%s.svg" % slug[1:]
    return "https://cdn.simpleicons.org/%s/8b5cf6" % slug


def stack(data):
    rows = []
    for g in data["stack"]:
        chips = " ".join('<code><img src="%s" width="14" height="14" alt="">&nbsp;%s</code>' % (icon(s), n.replace(" ", "&nbsp;"))
                         for n, s in g["items"])
        rows.append('<tr>\n<td valign="top"><sub><b>%s</b></sub></td>\n<td>%s</td>\n</tr>' % (g["group"], chips))
    return "<table>\n%s\n</table>" % "\n".join(rows)


def build(text, data):
    for name, fn in (("hackathons", hackathons), ("stack", stack)):
        block = "<!-- %s:start -->\n%s\n<!-- %s:end -->" % (name, fn(data), name)
        pat = re.compile(r"<!-- %s:start -->.*?<!-- %s:end -->" % (name, name), re.S)
        if not pat.search(text):
            sys.exit("README.md has no %s markers" % name)
        text = pat.sub(lambda _: block, text)
    return text


def main():
    readme = ROOT / "README.md"
    data = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    old = readme.read_text(encoding="utf-8")
    new = build(old, data)
    if "--check" in sys.argv:
        sys.exit(0 if new == old else "README.md is out of date: run python3 scripts/build_readme.py")
    if new != old:
        readme.write_text(new, encoding="utf-8")
        print("README.md updated")
    else:
        print("README.md already up to date")


if __name__ == "__main__":
    main()
