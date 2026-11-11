#!/usr/bin/env python3
"""Build the profile: vector images in assets/gen/ and the generated blocks of README.md, from data/profile.json.

    python3 scripts/build_readme.py          # write assets/gen/*.svg and README.md
    python3 scripts/build_readme.py --check  # exit 1 if anything is out of date

Every letter is an outlined path (an SVG inside <img> cannot load web fonts on GitHub), so the images are sharp at
any size and look the same everywhere. Needs: pip install fonttools uharfbuzz. Icons come from Simple Icons (CC0)
and are cached in assets/icons/. A new hackathon or tool is one entry in data/profile.json.
"""
import base64
import datetime
import io
import os
import subprocess
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
MONOGRAMS = {"@codex": "Cx", "@openai": "OA", "@watsonx": "wx", "@oracle": "Or", "@coldfusion": "CF", "@linkedin": "in"}


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


# ---------------------------------------------------------------- hackathon cards: one drawing per project
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


def motif(kind, c):
    """Line art in a 214x112 box, in the theme's violet."""
    v, d, tint = c["violet"], c["deep"], c["tint"]
    st = 'fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"' % v
    if kind == "car":  # a car under a detection box
        return ('<path %s d="M44 82 L56 62 Q61 55 72 55 L124 55 Q136 55 144 62 L160 76 L172 78 Q180 80 180 88 L180 90 '
                'L44 90 Z"/><path %s d="M70 62 L82 62 L82 74 L60 74 Z M92 62 L124 62 Q130 62 134 66 L141 74 L92 74 Z"/>'
                '<circle cx="76" cy="91" r="10" fill="%s" stroke="%s" stroke-width="2"/><circle cx="150" cy="91" r="10" fill="%s" stroke="%s" stroke-width="2"/>'
                '<rect x="134" y="66" width="44" height="40" rx="3" fill="none" stroke="%s" stroke-width="1.6" '
                'stroke-dasharray="4 4"/><circle cx="178" cy="66" r="4" fill="%s"/>'
                % (st, st, c["card"], v, c["card"], v, d, d))
    if kind == "route":  # a dotted route between neighbourhood shops
        pins = "".join('<circle cx="%d" cy="%d" r="%d" fill="%s"/>' % (x, y, r, col)
                       for x, y, r, col in ((32, 84, 6, d), (96, 52, 5, v), (138, 76, 5, v), (184, 34, 7, d)))
        shops = "".join('<rect x="%d" y="%d" width="9" height="9" rx="2" fill="%s" fill-opacity=".35"/>' % (x, y, tint)
                        for x, y in ((58, 30), (112, 92), (160, 54), (70, 94), (186, 82)))
        return ('<path d="M32 84 C56 40 80 46 96 52 S126 86 138 76 S170 30 184 34" fill="none" stroke="%s" '
                'stroke-width="2.4" stroke-linecap="round" stroke-dasharray="1 7"/>%s%s' % (v, shops, pins))
    if kind == "awning":  # a tianguis awning
        bands = "".join('<rect x="%d" y="26" width="17" height="30" fill="%s"%s/>' % (
            34 + i * 17, d if i % 2 == 0 else tint, "" if i % 2 == 0 else ' fill-opacity=".25"') for i in range(9))
        scal = "".join('<path d="M%d 56 a8.5 8.5 0 0 0 17 0" fill="%s"%s/>' % (
            34 + i * 17, d if i % 2 == 0 else tint, "" if i % 2 == 0 else ' fill-opacity=".25"') for i in range(9))
        return ('<rect x="30" y="20" width="161" height="8" rx="4" fill="%s"/>%s%s'
                '<path %s d="M38 64 L38 100 M183 64 L183 100 M28 100 L194 100"/>'
                '<rect x="62" y="80" width="22" height="14" rx="3" fill="%s" fill-opacity=".35"/>'
                '<rect x="96" y="76" width="30" height="18" rx="3" fill="%s" fill-opacity=".55"/>'
                '<rect x="138" y="82" width="18" height="12" rx="3" fill="%s" fill-opacity=".35"/>'
                % (v, bands, scal, st, tint, tint, tint))
    if kind == "voronoi":  # zones of the city, one picked
        cells = [("M20 18 L82 18 L72 58 L20 70 Z", ".10"), ("M82 18 L150 18 L132 50 L72 58 Z", ".22"),
                 ("M150 18 L196 18 L196 62 L132 50 Z", ".14"), ("M20 70 L72 58 L88 100 L20 100 Z", ".18"),
                 ("M72 58 L132 50 L146 92 L88 100 Z", "1"), ("M132 50 L196 62 L196 100 L146 92 Z", ".08"),
                 ("M146 92 L196 100 L146 100 Z", ".2")]
        out = "".join('<path d="%s" fill="%s" fill-opacity="%s" stroke="%s" stroke-width="1.6" stroke-linejoin="round"/>'
                      % (p, d if op == "1" else tint, op, c["card"]) for p, op in cells)
        return out + '<circle cx="110" cy="76" r="5" fill="%s"/><path %s d="M110 60 L110 50 M98 64 L91 57 M122 64 L129 57"/>' % (
            c["card"], 'fill="none" stroke="%s" stroke-width="2" stroke-linecap="round"' % c["card"])
    if kind == "leaf":  # a route that bends for cleaner air
        return ('<path d="M24 92 C70 92 76 40 120 44 S170 86 194 40" fill="none" stroke="%s" stroke-width="2.4" '
                'stroke-linecap="round"/><circle cx="24" cy="92" r="5" fill="%s"/><circle cx="194" cy="40" r="6" fill="%s"/>'
                '<path d="M150 22 C176 18 188 30 186 48 C164 52 148 42 150 22 Z" fill="%s" fill-opacity=".85"/>'
                '<path d="M154 26 L180 44" stroke="%s" stroke-width="1.6" stroke-linecap="round"/>'
                '<g fill="%s" fill-opacity=".25"><circle cx="58" cy="40" r="10"/><circle cx="72" cy="34" r="13"/>'
                '<circle cx="88" cy="40" r="9"/></g>' % (v, d, d, d, c["card"], tint))
    if kind == "wave":  # a voice
        hs = [6, 10, 16, 26, 38, 30, 20, 44, 58, 46, 32, 52, 64, 50, 36, 24, 40, 30, 18, 26, 14, 8, 12, 6]
        return "".join('<rect x="%d" y="%.1f" width="5" height="%d" rx="2.5" fill="%s"%s/>' % (
            25 + i * 7, 57 - h / 2, h, d if 7 <= i <= 13 else v, "" if 7 <= i <= 13 else ' fill-opacity=".55"')
            for i, h in enumerate(hs))
    if kind == "metro":  # two lines, two cities
        a = '<path d="M20 38 L96 38 L132 74 L196 74" fill="none" stroke="%s" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>' % d
        b2 = '<path d="M44 100 L44 70 L84 30 L196 30" fill="none" stroke="%s" stroke-width="5" stroke-opacity=".5" stroke-linecap="round" stroke-linejoin="round"/>' % v
        st_ = "".join('<circle cx="%d" cy="%d" r="5" fill="%s" stroke="%s" stroke-width="2.4"/>' % (x, y, c["card"], col)
                      for x, y, col in ((20, 38, d), (66, 38, d), (114, 56, d), (164, 74, d), (196, 74, d),
                                        (44, 100, v), (64, 50, v), (140, 30, v), (196, 30, v)))
        return a + b2 + st_
    # next: an open seat
    return ('<circle cx="107" cy="58" r="34" fill="none" stroke="%s" stroke-width="2" stroke-dasharray="5 6"/>%s'
            % (c["muted"], t("?", SANS, 700, 44, 107, 74, c["muted"], anchor="middle")))


def card(c, h, nxt=False):
    W, H = 214, 270
    b = ['<clipPath id="k"><rect x="1" y="1" width="%d" height="%d" rx="16"/></clipPath>' % (W - 2, H - 2),
         '<rect x="1" y="1" width="%d" height="%d" rx="16" fill="%s" stroke="%s"%s/>' % (
             W - 2, H - 2, c["card"], c["line"], ' stroke-dasharray="5 5"' if nxt else ""),
         '<g clip-path="url(#k)"><rect x="0" y="0" width="%d" height="118" fill="%s" fill-opacity="%s"/></g>' % (
             W, c["tint"], c["levels"][4])]
    b.append(motif(h.get("motif", "next"), c))
    # the medal
    big = h.get("big", "?")
    if not nxt:
        size = 13 if len(big) <= 2 else 9.5
        if h.get("first"):
            b.append('<circle cx="28" cy="28" r="17" fill="%s"/>' % c["deep"])
            b.append(t(big, SANS, 700, size, 28, 28 + size * 0.36, c["card"], anchor="middle"))
        else:
            b.append('<circle cx="28" cy="28" r="16" fill="%s" stroke="%s" stroke-width="2"/>' % (c["card"], c["violet"]))
            b.append(t(big, SANS, 700, size, 28, 28 + size * 0.36, c["violet"], anchor="middle"))
    ps = 21
    while ps > 15 and measure(h["project"], SANS, 700, ps, -0.02) > W - 36:
        ps -= 1
    b.append(t(h["project"], SANS, 700, ps, 18, 148, c["ink"], -0.02))
    sub = h["event"] if nxt else "%s · %s" % (h["award"], h["event"])
    ss = 11.5
    while ss > 8.5 and measure(sub, SANS, 500, ss) > W - 36:
        ss -= 0.25
    b.append(t(sub, SANS, 500, ss, 18, 168, c["violet"]))
    y = 192
    for line in wrap(h["pitch"], SANS, 400, 12, W - 36)[:3]:
        b.append(t(line, SANS, 400, 12, 18, y, c["muted"]))
        y += 17
    b.append('<path d="M18 %d L%d %d" stroke="%s" stroke-width="1"/>' % (H - 36, W - 18, H - 36, c["line"]))
    b.append(t((h["date"] + " · " + h["place"]).upper(), MONO, 500, 8.5, 18, H - 17, c["muted"], 0.1))
    if h.get("kit"):
        b.append(t("◆", MONO, 500, 11, W - 18, H - 16, c["violet"], anchor="end"))
    return svg(W, H, "%s · %s · %s · %s: %s" % (h["award"], h["event"], h["date"], h["project"], h["pitch"]), b)


# ---------------------------------------------------------------- stack: one section per theme
def stack(c, data):
    W, label_w, pill_h, gap, row_gap, pad = 900, 168, 36, 9, 10, 22
    b, y = [], 0
    for g_i, g in enumerate(data["stack"]):
        y += pad if g_i else 4
        top = y
        # pills, wrapped
        x, rows = label_w, 1
        pills = []
        for name, slug in g["items"]:
            w = 13 + 20 + 9 + measure(name, SANS, 500, 13.5) + 16
            if x + w > W:
                x, y, rows = label_w, y + pill_h + row_gap, rows + 1
            pills.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="18" fill="%s" fill-opacity="%s" '
                         'stroke="%s" stroke-opacity=".35"/>' % (x, y, w, pill_h, c["tint"], c["levels"][3], c["tint"])
                         + icon(slug, x + 13, y + 8, 20, c["deep"] if g_i == 0 else c["violet"])
                         + t(name, SANS, 500, 13.5, x + 13 + 20 + 9, y + 23, c["ink"]))
            x += w + gap
        b.append(t(g["group"].upper(), MONO, 500, 10.5, 0, top + 22, c["muted"], 0.14))
        b.append(t("%02d" % len(g["items"]), MONO, 500, 10.5, 0, top + 39, c["violet"], 0.14))
        b.extend(pills)
        y += pill_h
        if g_i < len(data["stack"]) - 1:
            b.append('<path d="M0 %.1f L%d %.1f" stroke="%s" stroke-width="1"/>' % (y + pad / 2 + 1, W, y + pad / 2 + 1, c["line"]))
    H = int(y + 14)
    return svg(W, H, "Stack. " + " ".join("%s: %s." % (g["group"], ", ".join(n for n, _ in g["items"]))
                                          for g in data["stack"]), b)


# ---------------------------------------------------------------- live numbers (GitHub API)
def gh_token():
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def gh_api(path, query=None):
    tok = gh_token()
    headers = {"User-Agent": "profile-readme-build", "Accept": "application/vnd.github+json"}
    if tok:
        headers["Authorization"] = "Bearer " + tok
    if query:
        req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query}).encode(),
                                     headers=headers, method="POST")
    else:
        req = urllib.request.Request("https://api.github.com/" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def live(data):
    """Stars, release and the contribution calendar; None where the API is not reachable (the old image stays)."""
    out = {"repos": {}, "calendar": None}
    for p in data["projects"]:
        if p.get("repo"):
            try:
                stars = gh_api("repos/" + p["repo"])["stargazers_count"]
                rel = gh_api("repos/%s/releases/latest" % p["repo"]).get("tag_name", "")
                out["repos"][p["repo"]] = (stars, rel)
            except Exception:  # noqa: BLE001
                pass
    try:
        q = ('query{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions '
             'weeks{contributionDays{date contributionCount}}}}}}' % data.get("user", "JoahanMorales"))
        out["calendar"] = gh_api("", q)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except Exception:  # noqa: BLE001
        pass
    return out


# ---------------------------------------------------------------- about, sections, projects, activity, contact
COLORS = {"i": "ink", "v": "violet", "m": "muted"}


def about(c, data):
    W, H = 640, 270
    b, y = [], 30
    for line in data["about"]:
        x = 0
        for text, style in line:
            d, w = text_path(text, SANS, 500 if style != "m" else 400, 18, x, y, -0.01)
            b.append('<path d="%s" fill="%s"/>' % (d, c[COLORS[style]]))
            x += w + 18 * -0.01
        y += 32
    y += 14
    b.append(t("EXPERIENCIA", MONO, 500, 10.5, 0, y, c["muted"], 0.16))
    y += 12
    for e in data["experience"]:
        b.append('<path d="M0 %.1f L%d %.1f" stroke="%s" stroke-width="1"/>' % (y, W - 8, y, c["line"]))
        y += 26
        d, w = text_path(e["role"], SANS, 700, 14.5, 0, y, -0.01)
        b.append('<path d="%s" fill="%s"/>' % (d, c["ink"]))
        b.append(t(e["org"], SANS, 400, 13, w + 10, y, c["muted"]))
        b.append(t(e["dates"].upper(), MONO, 500, 10, W - 8, y, c["violet"], 0.08, "end"))
        y += 14
    return svg(W, H, "Sobre mí. " + " ".join("".join(x for x, _ in l) for l in data["about"]), b)


def section(c, num, title):
    W, H = 900, 46
    b = [t("%02d" % num, MONO, 500, 11, 0, 30, c["violet"], 0.1)]
    d, w = text_path(title, SANS, 700, 24, 30, 31, -0.02)
    b.append('<path d="%s" fill="%s"/>' % (d, c["ink"]))
    b.append('<path d="M%.1f 23 L%d 23" stroke="%s" stroke-width="1"/>' % (30 + w + 16, W, c["line"]))
    return svg(W, H, title, b)


def project(c, p, live_repo):
    W, H = 440, 360
    img = (ROOT / p["image"]).read_bytes()
    uri = "data:image/jpeg;base64," + base64.b64encode(img).decode()
    b = ['<clipPath id="s"><rect x="14" y="14" width="%d" height="206" rx="10"/></clipPath>' % (W - 28),
         '<rect x="1" y="1" width="%d" height="%d" rx="16" fill="%s" stroke="%s"/>' % (W - 2, H - 2, c["card"], c["line"]),
         '<image href="%s" x="14" y="14" width="%d" height="206" preserveAspectRatio="xMidYMin slice" clip-path="url(#s)"/>'
         % (uri, W - 28)]
    b.append(t(p["name"], SANS, 700, 22, 18, 254, c["ink"], -0.02))
    y = 278
    for line in wrap(p["desc"], SANS, 400, 13, W - 36)[:2]:
        b.append(t(line, SANS, 400, 13, 18, y, c["muted"]))
        y += 18
    meta = []
    if live_repo:
        stars, rel = live_repo
        meta = ["%d stars" % stars] + ([rel] if rel else [])
    elif p.get("site"):
        meta = [p["site"]]
    x = 18
    for i, m in enumerate(meta + p["tags"]):
        col = c["violet"] if i < len(meta) else c["muted"]
        d, w = text_path(m.upper(), MONO, 500, 9.5, x, H - 22, 0.1)
        b.append('<path d="%s" fill="%s"/>' % (d, col))
        x += w + 14
    b.append('<path d="M18 %d L%d %d" stroke="%s" stroke-width="1"/>' % (H - 42, W - 18, H - 42, c["line"]))
    return svg(W, H, "%s: %s" % (p["name"], p["desc"]), b)


def activity(c, cal):
    W = 900
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    counts = [d["contributionCount"] for d in days]
    today = days[-1]["date"]
    cur = 0
    for n in reversed(counts[:-1] if counts[-1] == 0 else counts):
        if n == 0:
            break
        cur += 1
    best = run_ = 0
    for n in counts:
        run_ = run_ + 1 if n else 0
        best = max(best, run_)
    active = sum(1 for n in counts if n)
    stats = [("%s" % format(cal["totalContributions"], ",").replace(",", "."), "contribuciones en el último año"),
             ("%d" % cur, "días de racha actual"), ("%d" % best, "días, la racha más larga"), ("%d" % active, "días con commits")]
    b = []
    col_w = W / 4
    for i, (big, lab) in enumerate(stats):
        x = i * col_w
        b.append(t(big, SANS, 700, 34, x, 40, c["violet"] if i == 0 else c["ink"], -0.03))
        b.append(t(lab, SANS, 400, 12.5, x, 62, c["muted"]))
    cell, gap, top = 13, 4, 104
    weeks = cal["weeks"]
    peak = max(counts) or 1
    def level(n):
        if n == 0:
            return None
        r = n / peak
        return 3 if r > .5 else 2 if r > .25 else 1 if r > .08 else 0
    ops = [".35", ".55", ".78", "1"]
    last_m = None
    for wi, w in enumerate(weeks):
        x = wi * (cell + gap)
        first = w["contributionDays"][0]["date"]
        m = int(first[5:7])
        if m != last_m and wi < len(weeks) - 2:
            names = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
            b.append(t(names[m - 1], MONO, 400, 9.5, x, top - 10, c["muted"]))
            last_m = m
        for d in w["contributionDays"]:
            r = datetime.date.fromisoformat(d["date"]).isoweekday() % 7
            lv = level(d["contributionCount"])
            if lv is None:
                b.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" fill-opacity="%s"/>' % (
                    x, top + r * (cell + gap), cell, cell, c["tint"], c["levels"][4]))
            else:
                b.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" fill-opacity="%s"/>' % (
                    x, top + r * (cell + gap), cell, cell, c["deep"], ops[lv]))
    H = top + 7 * (cell + gap) + 4
    return svg(W, H, "Actividad: %d contribuciones en el último año, racha actual de %d días, la más larga de %d días (hasta %s)"
               % (cal["totalContributions"], cur, best, today), b)


def button(c, ct):
    lab_w = measure(ct["label"].upper(), MONO, 500, 10, 0.12)
    val_w = measure(ct["value"], SANS, 500, 14)
    W, H = int(16 + 20 + 12 + lab_w + 12 + val_w + 30), 44
    b = ['<rect x="1" y="1" width="%d" height="%d" rx="22" fill="%s" stroke="%s"/>' % (W - 2, H - 2, c["card"], c["line"])]
    b.append(icon(ct["icon"], 16, 12, 20, c["violet"]))
    b.append(t(ct["label"].upper(), MONO, 500, 10, 48, 26, c["muted"], 0.12))
    b.append(t(ct["value"], SANS, 500, 14, 48 + lab_w + 12, 27, c["ink"]))
    b.append(t("↗", SANS, 500, 13, W - 16, 27, c["violet"], anchor="end"))
    return svg(W, H, "%s: %s" % (ct["label"], ct["value"]), b)


# ---------------------------------------------------------------- the README
def picture(name, alt, width, href=None):
    pic = ('<picture><source media="(prefers-color-scheme: dark)" srcset="assets/gen/%s-dark.svg">'
           '<img src="assets/gen/%s-light.svg" width="%s" alt="%s"></picture>'
           % (name, name, width, escape(alt, {'"': "&quot;"})))
    return '<a href="%s">%s</a>' % (href, pic) if href else pic


def slug(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower().replace("×", "x")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def hk_name(h):
    return "hk-" + slug(h["project"] + "-" + h["event"])


SECTIONS = ["Proyectos", "Hackathons", "Stack", "Actividad", "Contacto"]


def render(data, lv):
    files = {}
    hk = len(data["hackathons"])
    for theme, c in THEMES.items():
        files["header-%s.svg" % theme] = header(c, hk)
        files["about-%s.svg" % theme] = about(c, data)
        files["stack-%s.svg" % theme] = stack(c, data)
        for i, name in enumerate(SECTIONS, 1):
            files["sec-%s-%s.svg" % (slug(name), theme)] = section(c, i, name)
        for h in data["hackathons"]:
            files["%s-%s.svg" % (hk_name(h), theme)] = card(c, h)
        for p in data["projects"]:
            files["pr-%s-%s.svg" % (slug(p["name"]), theme)] = project(c, p, lv["repos"].get(p.get("repo")))
        if lv["calendar"]:
            files["activity-%s.svg" % theme] = activity(c, lv["calendar"])
        for ct in data["contact"]:
            files["ct-%s-%s.svg" % (slug(ct["label"]), theme)] = button(c, ct)
    sec = lambda n: picture("sec-" + slug(n), n, "100%")
    cards = [picture(hk_name(h), "%s · %s · %s" % (h["award"], h["event"], h["project"]), "24%", h.get("url") or None)
             for h in data["hackathons"]]
    rows = ["\n".join(cards[i:i + 4]) for i in range(0, len(cards), 4)]
    projects = "\n".join(picture("pr-" + slug(p["name"]), p["name"], "49%", p["url"]) for p in data["projects"])
    contact = "\n".join(picture("ct-" + slug(ct["label"]), "%s: %s" % (ct["label"], ct["value"]), None, ct["url"])
                        .replace(' width="None"', "") for ct in data["contact"])
    readme = "\n\n".join([
        "<!-- Generated by scripts/build_readme.py from data/profile.json. Edit those, not this file. -->",
        picture("header", "Joahan Morales · AI Engineer, Full Stack, Backend", "100%"),
        '<p>\n%s\n<img src="%s" width="29%%" alt="Coding cat">\n</p>'
        % (picture("about", "Sobre mí", "69%"), data.get("cat", "https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif")),
        sec("Proyectos"), '<p align="center">\n%s\n</p>' % projects,
        sec("Hackathons"), '<p align="center">\n%s\n</p>' % "\n<br>\n".join(rows),
        sec("Stack"), picture("stack", "Stack", "100%"),
        sec("Actividad"), picture("activity", "Actividad en GitHub", "100%"),
        sec("Contacto"), "<p>\n%s\n</p>" % contact,
        '<p align="right"><img src="https://komarev.com/ghpvc/?username=JoahanMorales&label=visitas&color=8b5cf6&style=flat" alt="visitas"></p>',
    ]) + "\n"
    return files, readme


def main():
    data = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    lv = live(data)
    files, readme = render(data, lv)
    GEN.mkdir(parents=True, exist_ok=True)
    keep = {"activity-dark.svg", "activity-light.svg"} if not lv["calendar"] else set()
    stale = [f for f, body in files.items() if not (GEN / f).exists() or (GEN / f).read_text(encoding="utf-8") != body]
    orphans = [p.name for p in GEN.glob("*.svg") if p.name not in files and p.name not in keep]
    old = (ROOT / "README.md").read_text(encoding="utf-8")
    if "--check" in sys.argv:
        if stale or orphans or readme != old:
            sys.exit("out of date: %s" % ", ".join(stale + orphans + (["README.md"] if readme != old else [])))
        return
    for f in stale:
        (GEN / f).write_text(files[f], encoding="utf-8")
    for f in orphans:
        (GEN / f).unlink()
    if readme != old:
        (ROOT / "README.md").write_text(readme, encoding="utf-8")
    print("wrote %d image(s), removed %d, README %s" % (len(stale), len(orphans), "updated" if readme != old else "unchanged"))


if __name__ == "__main__":
    main()
