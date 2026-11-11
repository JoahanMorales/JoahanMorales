#!/usr/bin/env python3
"""Build the profile: vector images in assets/gen/ and the generated blocks of README.md, from data/profile.json.

    python3 scripts/build_readme.py          # write assets/gen/*.svg and README.md
    python3 scripts/build_readme.py --check  # exit 1 if anything is out of date

Every letter is an outlined path (an SVG inside <img> cannot load web fonts on GitHub), so the images are sharp at
any size and look the same everywhere. Needs: pip install fonttools uharfbuzz. Icons come from Simple Icons (CC0)
and are cached in assets/icons/. A new hackathon or tool is one entry in data/profile.json.
"""
import io
import json
import re
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "assets" / "gen"
SANS, MONO = "SpaceGrotesk.ttf", "JetBrainsMono.ttf"

THEMES = {
    "dark": {"ink": "#E9E6F2", "muted": "#8E86A3", "violet": "#A78BFA", "deep": "#8B5CF6", "card": "#13111B",
             "line": "#2A2438", "tint": "#8B5CF6", "levels": [".30", ".20", ".13", ".08", ".045"]},
    "light": {"ink": "#16121F", "muted": "#6B6480", "violet": "#6D28D9", "deep": "#7C3AED", "card": "#FBFAFF",
              "line": "#E4DEF5", "tint": "#7C3AED", "levels": [".20", ".13", ".085", ".05", ".025"]},
}

# ---------------------------------------------------------------- text as paths
_faces = {}


def _face(name, wght):
    if (name, wght) not in _faces:
        tt = instancer.instantiateVariableFont(TTFont(ROOT / "assets" / "fonts" / name), {"wght": wght})
        buf = io.BytesIO()
        tt.save(buf)
        data = buf.getvalue()
        _faces[(name, wght)] = (TTFont(io.BytesIO(data)), hb.Font(hb.Face(data)))
    return _faces[(name, wght)]


def text_path(text, font, wght, size, x, y, track=0.0, anchor="start"):
    """Outlines of `text` with its baseline at (x, y); track = letter-spacing in em. Returns (d, width)."""
    tt, hbf = _face(font, wght)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbf, buf, {"kern": True, "liga": True})
    scale = size / tt["head"].unitsPerEm
    width = sum(p.x_advance for p in buf.glyph_positions) * scale + track * size * max(len(buf.glyph_infos) - 1, 0)
    x -= {"start": 0, "middle": width / 2, "end": width}[anchor]
    glyphs, order = tt.getGlyphSet(), tt.getGlyphOrder()
    pen = SVGPathPen(glyphs, ntos=lambda v: ("%.2f" % v).rstrip("0").rstrip("."))
    cx = x
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs[order[info.codepoint]].draw(
            TransformPen(pen, (scale, 0, 0, -scale, cx + pos.x_offset * scale, y - pos.y_offset * scale)))
        cx += pos.x_advance * scale + track * size
    return pen.getCommands(), width


def measure(text, font, wght, size, track=0.0):
    return text_path(text, font, wght, size, 0, 0, track)[1]


def t(text, font, wght, size, x, y, fill, track=0.0, anchor="start", opacity=None):
    d, _ = text_path(text, font, wght, size, x, y, track, anchor)
    op = ' fill-opacity="%s"' % opacity if opacity else ""
    return '<path d="%s" fill="%s"%s/>' % (d, fill, op)


def svg(w, h, title, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img">'
            "<title>%s</title>%s</svg>\n" % (w, h, w, h, escape(title), "".join(body)))


# ---------------------------------------------------------------- icons
MONOGRAMS = {"@codex": "Cx", "@openai": "OA", "@watsonx": "wx", "@oracle": "Or", "@coldfusion": "CF"}


def icon_path(slug):
    """The single path of a Simple Icons glyph (24x24), cached in assets/icons/si-SLUG.svg."""
    cache = ROOT / "assets" / "icons" / ("si-%s.svg" % slug)
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request("https://cdn.simpleicons.org/%s" % slug, headers={"User-Agent": "profile-readme-build"})
        with urllib.request.urlopen(req, timeout=30) as r:
            cache.write_bytes(r.read())
    return re.search(r' d="([^"]+)"', cache.read_text(encoding="utf-8")).group(1)


def icon(slug, x, y, size, color):
    s = size / 24
    if slug.startswith("@"):  # no public logo: a monogram in the same style
        return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="none" stroke="%s" stroke-width="%.1f"/>'
                % (x + 1.5 * s, y + 1.5 * s, 21 * s, 21 * s, 5 * s, color, 1.8 * s)
                + t(MONOGRAMS[slug], MONO, 700, 9.5 * s, x + size / 2, y + 15.6 * s, color, anchor="middle"))
    return '<path transform="translate(%.1f %.1f) scale(%.4f)" d="%s" fill="%s"/>' % (x, y, s, icon_path(slug), color)


# ---------------------------------------------------------------- header
SEVEN = {(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (2, 5), (3, 4), (4, 3), (5, 3)}


def header(c, hk):
    W, H = 900, 200
    b = []
    d, w = text_path("Joahan Morales", SANS, 700, 76, 2, 88, -0.035)
    b.append('<path d="%s" fill="%s"/>' % (d, c["ink"]))
    b.append(t(".", SANS, 700, 76, 2 + w + 76 * -0.035, 88, c["violet"]))
    x = 4
    for text, col in (("AI Engineer", c["violet"]), (" / ", c["muted"]), ("Full Stack", c["ink"]),
                      (" / ", c["muted"]), ("Backend", c["ink"])):
        d, w = text_path(text, SANS, 500, 21, x, 128, -0.01)
        b.append('<path d="%s" fill="%s"/>' % (d, col))
        x += w + 21 * -0.01
    b.append(t("IPN  ·  IBM Z Student Ambassador  ·  Presidente de UPIIXIA", MONO, 400, 12.5, 4, 160, c["muted"], 0.02))
    cell, gap = 18, 5
    gx, gy = W - 8 - (7 * cell + 6 * gap), 6
    for r in range(7):
        for col in range(7):
            on = (r, col) in SEVEN
            b.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s"%s/>' % (
                gx + col * (cell + gap), gy + r * (cell + gap), cell, cell, c["deep"] if on else c["tint"],
                "" if on else ' fill-opacity="%s"' % c["levels"][4]))
    cx, cy = gx + (7 * cell + 6 * gap) / 2, gy + 7 * cell + 6 * gap + 22
    w1 = measure("%d× " % hk, MONO, 500, 11, 0.16)
    w2 = measure("HACKATHON WINNER", MONO, 500, 11, 0.16)
    b.append(t("%d× " % hk, MONO, 500, 11, cx - (w1 + w2) / 2, cy, c["violet"], 0.16))
    b.append(t("HACKATHON WINNER", MONO, 500, 11, cx - (w1 + w2) / 2 + w1, cy, c["muted"], 0.16))
    return svg(W, H, "Joahan Morales · AI Engineer, Full Stack, Backend · %d× hackathon winner" % hk, b)


# ---------------------------------------------------------------- hackathon cards (a scoreboard)
def wrap(text, font, wght, size, width):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if cur and measure(trial, font, wght, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def card(c, h, nxt=False):
    W, H = 440, 236
    b = ['<clipPath id="k"><rect x="1" y="1" width="%d" height="%d" rx="18"/></clipPath>' % (W - 2, H - 2),
         '<rect x="1" y="1" width="%d" height="%d" rx="18" fill="%s" stroke="%s"%s/>' % (
             W - 2, H - 2, c["card"], c["line"], ' stroke-dasharray="6 6"' if nxt else "")]
    big = h.get("big", "?")
    fill, op = (c["deep"], ".9") if h.get("first") else (c["violet"], ".5")
    if nxt:
        fill, op = c["muted"], ".3"
    size = 172 if len(big) <= 2 else 112
    b.append('<g clip-path="url(#k)">%s</g>' % t(big, SANS, 700, size, W + 16, 212, fill, -0.06, "end", op))
    b.append(t((h["date"] + "  ·  " + h["place"]).upper(), MONO, 500, 10.5, 26, 40, c["muted"], 0.12))
    b.append(t(h["award"], MONO, 500, 12, 26, 70, c["violet"], 0.02))
    b.append(t(h["event"], SANS, 700, 17, 26, 96, c["ink"], -0.01))
    ps = 34
    while ps > 22 and measure(h["project"], SANS, 700, ps, -0.03) > 262:
        ps -= 1
    b.append(t(h["project"], SANS, 700, ps, 25, 148, c["ink"] if nxt else c["violet"], -0.03))
    y = 174
    for line in wrap(h["pitch"], SANS, 400, 13.5, 240)[:2]:
        b.append(t(line, SANS, 400, 13.5, 26, y, c["muted"]))
        y += 19
    if h.get("kit"):
        b.append(t("◆ UPIIXIA AGENTIC KIT", MONO, 500, 9.5, 26, H - 20, c["violet"], 0.12, opacity=".85"))
    return svg(W, H, "%s · %s · %s · %s: %s" % (h["award"], h["event"], h["date"], h["project"], h["pitch"]), b)


# ---------------------------------------------------------------- stack: a periodic table of tools
def stack(c, data):
    cols, tile, gap, top = 9, 94, 6, 40
    items = [(g_i, n, s) for g_i, g in enumerate(data["stack"]) for n, s in g["items"]]
    rows = (len(items) + cols - 1) // cols
    W = cols * tile + (cols - 1) * gap
    H = top + rows * (tile + gap) - gap
    b, x = [], 0
    for g_i, g in enumerate(data["stack"]):
        b.append('<rect x="%.1f" y="6" width="12" height="12" rx="3" fill="%s" fill-opacity="%s"/>' % (
            x, c["tint"], max(float(c["levels"][g_i]) * 2.2, 0.12)))
        d, w = text_path(g["group"].upper(), MONO, 500, 10.5, x + 19, 16, 0.12)
        b.append('<path d="%s" fill="%s"/>' % (d, c["muted"]))
        x += 19 + w + 28
    for i, (g_i, name, slug) in enumerate(items):
        tx, ty = (i % cols) * (tile + gap), top + (i // cols) * (tile + gap)
        b.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="%s" fill-opacity="%s"/>' % (
            tx, ty, tile, tile, c["tint"], c["levels"][g_i]))
        b.append(t("%02d" % (i + 1), MONO, 500, 9, tx + 10, ty + 17, c["muted"], 0.05, opacity=".8"))
        b.append(icon(slug, tx + tile / 2 - 13, ty + 24, 26, c["deep"] if g_i == 0 else c["violet"]))
        size = 11.5 if measure(name, SANS, 500, 11.5) < tile - 12 else 10
        b.append(t(name, SANS, 500, size, tx + tile / 2, ty + tile - 14, c["ink"], anchor="middle"))
    return svg(W, H, "Stack. " + " ".join("%s: %s." % (g["group"], ", ".join(n for n, _ in g["items"]))
                                          for g in data["stack"]), b)


# ---------------------------------------------------------------- README blocks
def picture(name, alt, width, href=None):
    pic = ('<picture><source media="(prefers-color-scheme: dark)" srcset="assets/gen/%s-dark.svg">'
           '<img src="assets/gen/%s-light.svg" width="%s" alt="%s"></picture>'
           % (name, name, width, escape(alt, {'"': "&quot;"})))
    return '<a href="%s">%s</a>' % (href, pic) if href else pic


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def render(data):
    files = {}
    hk, n = len(data["hackathons"]), data.get("next")
    for theme, c in THEMES.items():
        files["header-%s.svg" % theme] = header(c, hk)
        files["stack-%s.svg" % theme] = stack(c, data)
        for h in data["hackathons"]:
            files["hk-%s-%s.svg" % (slug(h["project"]), theme)] = card(c, h)
        if n:
            files["hk-next-%s.svg" % theme] = card(c, dict(n, big="?"), nxt=True)
    cards = [picture("hk-" + slug(h["project"]), "%s · %s · %s" % (h["award"], h["event"], h["project"]), "49%",
                     h.get("url") or None) for h in data["hackathons"]]
    if n:
        cards.append(picture("hk-next", n["event"], "49%", n.get("url")))
    pairs = ["\n".join(cards[i:i + 2]) for i in range(0, len(cards), 2)]
    blocks = {"header": picture("header", "Joahan Morales · AI Engineer, Full Stack, Backend", "100%"),
              "hackathons": '<p align="center">\n%s\n</p>' % "\n<br>\n".join(pairs),
              "stack": picture("stack", "Stack", "100%")}
    return files, blocks


def main():
    data = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    files, blocks = render(data)
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    new = text
    for name, block in blocks.items():
        pat = re.compile(r"<!-- %s:start -->.*?<!-- %s:end -->" % (name, name), re.S)
        if not pat.search(new):
            sys.exit("README.md has no %s markers" % name)
        new = pat.sub(lambda _: "<!-- %s:start -->\n%s\n<!-- %s:end -->" % (name, block, name), new)
    GEN.mkdir(parents=True, exist_ok=True)
    stale = [f for f, body in files.items() if not (GEN / f).exists() or (GEN / f).read_text(encoding="utf-8") != body]
    orphans = [p.name for p in GEN.glob("*.svg") if p.name not in files]
    if "--check" in sys.argv:
        if stale or orphans or new != text:
            sys.exit("out of date: %s" % ", ".join(stale + orphans + (["README.md"] if new != text else [])))
        return
    for f in stale:
        (GEN / f).write_text(files[f], encoding="utf-8")
    for f in orphans:
        (GEN / f).unlink()
    if new != text:
        readme.write_text(new, encoding="utf-8")
    print("wrote %d image(s), removed %d, README %s" % (len(stale), len(orphans), "updated" if new != text else "unchanged"))


if __name__ == "__main__":
    main()
