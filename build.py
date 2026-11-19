#!/usr/bin/env python3
"""Build the Study In Korea site.

Reads data/programs.json, data/site.json and src/, writes the finished site to dist/.
Uses only the Python standard library, so it runs on any Mac with Python 3:

    python3 build.py

Image conversion (WebP) and font subsetting are separate one-off steps in
tools/prepare_assets.py; their output is committed in src/assets/.
"""
import datetime
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
TPL = SRC / "templates"
DIST = ROOT / "dist"
SITE_URL = "https://www.aqibinkorea.com/"

CATEGORIES = [("bachelors", "Bachelors"), ("masters", "Masters"), ("phd", "PhD")]


# ---------------------------------------------------------------- helpers
def esc(s):
    """Escape text for HTML (keeps quotes readable; we escape them only in attributes)."""
    return html.escape(s, quote=False)


def attr(s):
    return html.escape(s, quote=True)


def tpl(name, **values):
    text = (TPL / name).read_text(encoding="utf-8")
    return fill(text, values, name)


def fill(text, values, name="template"):
    def rep(m):
        key = m.group(1)
        if key not in values:
            raise KeyError(f"{name}: no value for {{{{{key}}}}}")
        return str(values[key])
    return re.sub(r"\{\{(\w+)\}\}", rep, text)


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def short_level(level):
    """First line of a level name: 'Masters\\n(1 day class per week)' -> 'Masters'."""
    return level["name"].split("\n")[0]


# ---------------------------------------------------------------- data
def load():
    programs = json.loads((ROOT / "data/programs.json").read_text(encoding="utf-8"))
    site = json.loads((ROOT / "data/site.json").read_text(encoding="utf-8"))
    latest = ROOT / "data/latest_videos.json"  # filled every night by tools/fetch_videos.py
    store = json.loads(latest.read_text(encoding="utf-8")) if latest.exists() else {"videos": []}
    own = store.get("overrides", {})  # the owner's own headline for a video always wins
    hide = set(store.get("hidden", []))  # clips of a long video, and any the owner hides
    site["latest"] = [dict(v, title=own.get(v["id"], v["title"])) for v in store["videos"]
                      if not v.get("clip_of") and v["id"] not in hide]
    return programs, site


def all_programs(data):
    for u in data["universities"]:
        for lv in u["levels"]:
            for p in lv["programs"]:
                yield u, lv, p


def first_deadline(level):
    return level["deadlines"][0] if level["deadlines"] else None


def uni_deadline(uni):
    dates = [first_deadline(lv) for lv in uni["levels"] if first_deadline(lv)]
    return min(dates) if dates else None


# ---------------------------------------------------------------- small parts
def logo(uni, extra=""):
    cls = f"logo {extra} lg-{uni['slug']}".replace("  ", " ") if extra else f"logo lg-{uni['slug']}"
    return f'<span class="{cls}" role="img" aria-label="{attr(uni["name"])} logo"></span>'


def city(uni):
    return f'<p class="city">{esc(uni["city"])} <span lang="ko">{esc(uni["city_ko"])}</span></p>'


def deadline_td(iso):
    if not iso:
        return ""
    return (f'<p class="td"><span class="lbl">Deadline</span>'
            f'<span class="dl" data-date="{iso}">{nice_date(iso)}</span></p>')


def names_summary(programs, limit=3):
    names = [p["name"] for p in programs[:limit]]
    more = " and more" if len(programs) > limit else ""
    return esc(", ".join(names)) + more


def uni_tile(uni):
    progs = [p for lv in uni["levels"] for p in lv["programs"]]
    chips = "".join(f"<li>{esc(short_level(lv))}</li>" for lv in uni["levels"])
    return (f'<a class="tile ucard" href="#uni-{uni["slug"]}">{logo(uni)}{city(uni)}'
            f'<h3>{esc(uni["name"])}</h3>'
            f'<ul class="lvchips" aria-label="Degree levels">{chips}</ul>'
            f'<p class="tm"><b>{plural(len(progs), "course")}</b> including {names_summary(progs)}</p>'
            f'{deadline_td(uni_deadline(uni))}<span class="ubtn">Explore Details</span></a>')


def degree_tiles(data):
    out = []
    for key, label in CATEGORIES:
        unis = [u for u in data["universities"] if any(key in lv["categories"] for lv in u["levels"])]
        n = sum(len(lv["programs"]) for u in unis for lv in u["levels"] if key in lv["categories"])
        out.append(f'<a class="tile big" href="#{key}"><h3>{label}</h3>'
                   f'<p class="tm">{plural(len(unis), "university").replace("universitys", "universities")}</p>'
                   f'<p class="tm">{plural(n, "course")}</p><span class="go">View {label}</span></a>')
    return "".join(out)


def socials(site, kind):
    s = site["socials"]
    order = ["youtube", "instagram", "tiktok", "facebook"]
    cls = {"youtube": "yt", "instagram": "ig", "tiktok": "tt", "facebook": "fb"}
    if kind == "big":
        return "".join(f'<a class="sb {cls[k]}" href="{attr(s[k]["url"])}"><b>{esc(s[k]["label"])}</b>'
                       f'<i>{esc(s[k]["handle"])}</i></a>' for k in order)
    return "".join(f'<a class="{cls[k]}" href="{attr(s[k]["url"])}">{esc(s[k]["label"])}</a>' for k in order)


# ---------------------------------------------------------------- pages
def page_university(uni):
    tiles = []
    for lv in uni["levels"]:
        tiles.append(f'<a class="tile" href="#uni-{uni["slug"]}-{lv["slug"]}"><h3 class="pre">{esc(lv["name"])}</h3>'
                     f'<p class="tm">{plural(len(lv["programs"]), "course")}</p>'
                     f'<p class="tm">{names_summary(lv["programs"])}</p>'
                     f'{deadline_td(first_deadline(lv))}<span class="go">View courses</span></a>')
    return (f'<section class="page" id="p-uni-{uni["slug"]}" data-nav="universities"><div class="wrap">'
            f'<nav class="crumb" aria-label="Breadcrumb"><a href="#universities">Universities</a><span>{esc(uni["name"])}</span></nav>'
            f'<header class="ph">{logo(uni, "lgc")}{city(uni)}<h1>{esc(uni["name"])}</h1>'
            f'<p class="sub">Choose a degree to see its courses, fees and requirements.</p></header>'
            f'<div class="tiles" data-passed-last>{"".join(tiles)}</div></div></section>')


def prog_cell(p):
    details = "".join(f'<span class="pm">{esc(d)}</span>' for d in p["details"])
    return f'<td class="prog"><span class="pn">{esc(p["name"])}</span>{details}</td>'


def fee_cells(p):
    if p.get("tuition_combined"):
        return f'<td colspan="2" class="fee">{esc(p["tuition_combined"])}</td>'
    return f'<td class="fee">{esc(p["tuition_krw"] or "—")}</td><td class="fee">{esc(p["tuition_usd"] or "—")}</td>'


def fact_value(entries):
    out = []
    for e in entries:
        if "krw" in e or "usd" in e:
            for unit, key in (("KRW", "krw"), ("USD (Approx.)", "usd")):
                out.append(f'<p class="v"><span class="unit">{unit}</span>{esc(e.get(key) or "—")}</p>')
        else:
            out.append(f'<p class="v">{esc(e.get("value") or "—")}</p>')
    return "".join(out)


def fact(label, entries, wide=False, note=""):
    note = f'<p class="kuacnote">{esc(note)}</p>' if note else ""
    return f'<div class="fact {"wide" if wide else ""}"><dt>{esc(label)}</dt><dd>{fact_value(entries)}{note}</dd></div>'


def page_level(data, site, uni, lv):
    L = data["labels"]
    rows = "".join(f"<tr>{prog_cell(p)}{fee_cells(p)}</tr>" for p in lv["programs"])
    f = lv["facts"]
    facts = (fact(L["requirements"], f["requirements"])
             + fact(L["scholarship"], f["scholarship"], wide=True)
             + fact(L["dormitory"], f["dormitory"])
             + fact(L["application_fee"], f["application_fee"])
             + fact(L["enrollment_fee"], f["enrollment_fee"],
                    note=site["kuac_note"] if any("KUAC" in (e.get("value") or "") for e in f["enrollment_fee"]) else "")
             + fact(L["visa_from_korea"], f["visa_from_korea"]))
    dl = first_deadline(lv)
    facts += (f'<div class="fact "><dt>{esc(L["deadline"])}</dt><dd><p class="v dl" data-date="{dl}">{nice_date(dl)}</p></dd></div>'
              if dl else f'<div class="fact "><dt>{esc(L["deadline"])}</dt><dd><p class="v">—</p></dd></div>')
    facts += (f'<div class="fact wa"><dt class="vh">Contact</dt>'  # label for screen readers; keeps the list valid
              f'<dd><a class="wabtn" href="{attr(site["whatsapp"])}">Message me on WhatsApp</a></dd></div>')
    others = [o for o in uni["levels"] if o is not lv]
    sib = ""
    if others:
        sib = ('<p class="sib">Other degrees at this university: '
               + "".join(f'<a href="#uni-{uni["slug"]}-{o["slug"]}">{esc(short_level(o))}</a>' for o in others) + "</p>")
    uhd = (f'<div class="uhd"><span class="lbl">Deadline</span><span class="dl" data-date="{dl}">{nice_date(dl)}</span></div>'
           if dl else "")
    return (f'<section class="page" id="p-uni-{uni["slug"]}-{lv["slug"]}" data-nav="universities"><div class="wrap">'
            f'<nav class="crumb" aria-label="Breadcrumb"><a href="#universities">Universities</a>'
            f'<a href="#uni-{uni["slug"]}">{esc(uni["name"])}</a><span>{esc(short_level(lv))}</span></nav>'
            f'<div class="uni"><header class="uh"><div>{logo(uni)}{city(uni)}'
            f'<h1 class="pre">{esc(lv["name"])}</h1><p class="at">{esc(uni["name"])}</p></div>{uhd}</header>'
            f'<h2 class="ch">Courses <span>{len(lv["programs"])}</span></h2>'
            f'<div class="tw"><table><thead><tr><th rowspan="2">{esc(L["programs"])}</th>'
            f'<th colspan="2">{esc(L["tuition"])}</th></tr><tr><th>KRW</th><th>USD (Approx.)</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div><dl class="facts">{facts}</dl></div>{sib}</div></section>')


def page_degree(data, key, label):
    tiles = []
    for u in data["universities"]:
        for lv in u["levels"]:
            if key not in lv["categories"]:
                continue
            tiles.append(f'<a class="tile" href="#uni-{u["slug"]}-{lv["slug"]}">{logo(u)}{city(u)}'
                         f'<h3>{esc(u["name"])}</h3><p class="tm pre">{esc(lv["name"])}</p>'
                         f'<p class="tm">{plural(len(lv["programs"]), "course")}</p>'
                         f'{deadline_td(first_deadline(lv))}<span class="go">View courses</span></a>')
    return (f'<section class="page" id="p-{key}" data-nav="degrees"><div class="wrap">'
            f'<nav class="crumb" aria-label="Breadcrumb"><a href="#degrees">Degrees</a><span>{label}</span></nav>'
            f'<header class="ph"><h1>{label}</h1><p class="sub">Universities offering {label} programs for '
            f'{esc(data["intake"])}. Choose one to see its courses.</p></header>'
            f'<div class="tiles" data-passed-last>{"".join(tiles)}</div></div></section>')


def fee_summary(p):
    if p.get("tuition_combined"):
        return p["tuition_combined"].replace("\n", " ")
    parts = [x.replace("\n", " ") for x in (p["tuition_krw"], p["tuition_usd"]) if x]
    return " / ".join(parts)


def course_rows(data):
    rows = []
    for u, lv, p in all_programs(data):
        search = " ".join([p["name"] + ("\n" + "\n".join(p["details"]) if p["details"] else ""),
                           u["name"], u["city"], lv["name"]]).lower()
        details = "".join(f'<span class="pm">{esc(d)}</span>' for d in p["details"])
        dl = first_deadline(lv)
        rows.append(f'<a class="crs" href="#uni-{u["slug"]}-{lv["slug"]}" data-city="{attr(u["city"])}" '
                    + (f'data-date="{dl}" ' if dl else "") +
                    f'data-tags="{" ".join(lv["categories"])}" data-t="{esc(search)}">'
                    f'<span class="c1"><span class="pn">{esc(p["name"])}</span>{details}</span>'
                    f'<span class="c2"><b>{esc(u["name"])}</b>{esc(short_level(lv))} · {esc(u["city"])}</span>'
                    f'<span class="c3">{esc(fee_summary(p))}</span></a>')
    return "".join(rows)


def city_chips(data):
    cities = []
    for u in data["universities"]:
        if u["city"] not in cities:
            cities.append(u["city"])
    return "".join(f'<button type="button" class="chip" data-city="{attr(c)}">{esc(c)}</button>' for c in cities)


LATEST_ON_PAGE = 6   # newest uploads shown on the Videos page ("Latest videos")
HOME_CARDS = 6       # video cards on Home: the owner's "start here" videos first, then the newest uploads
SUBSCRIBE = "https://www.youtube.com/@aqibinkorea?sub_confirmation=1"  # opens YouTube's subscribe box


def all_videos(site):
    """Every video by id: nightly uploads and hand-written ones, with a short text when there is one."""
    out = {}
    for v in site["videos"]:
        first = re.match(r"\s*<p>(.*?)</p>", v.get("description_html", ""), re.S)  # its opening paragraph
        text = html.unescape(re.sub(r"<[^>]+>", "", first.group(1))).strip() if first else ""
        if text.endswith(":"):  # leads into a list: too little on its own
            text = ""
        out[v["youtube_id"]] = {"id": v["youtube_id"], "title": v["title"], "url": v["url"],
                                "description": text, "published": ""}
    for v in site["latest"]:
        out[v["id"]] = {"id": v["id"], "title": v["title"], "url": v["url"],
                        "description": v.get("description", ""), "published": v.get("published", "")}
    return out


def featured(site):
    """The owner's "start here" order (data/site.json "featured"), skipping ids that are not known."""
    vids = all_videos(site)
    return [vids[i] for i in site.get("featured", []) if i in vids]


def video_card(v, thumbs, extra="", details=False):
    """A card that plays the video in place (site.js swaps the cover for YouTube's player on click),
    with links to comment on it and to subscribe on YouTube. Without scripts the cover opens YouTube."""
    text = ""
    if details:
        date = f'<time datetime="{v["published"]}">{nice_date(v["published"])}</time>' if v["published"] else ""
        desc = f'<span class="lvd">{esc(v["description"])}</span>' if v["description"] else ""
        text = f'<span class="lvt">{date}<b>{esc(v["title"])}</b>{desc}</span>'
    else:
        text = f'<b>{esc(v["title"])}</b>'
    return (f'<div class="vcard{extra}"><a class="vthumb" href="{attr(v["url"])}" data-yt="{attr(v["id"])}" '
            f'aria-label="Play video: {attr(v["title"])}">{thumbs({"youtube_id": v["id"]})}'
            f'<i class="vplay" aria-hidden="true"></i></a>{text}'
            f'<span class="vact"><a href="{attr(v["url"])}">Comment<span class="vlong"> on YouTube</span></a>'
            f'<a href="{SUBSCRIBE}">Subscribe</a></span></div>')


def video_cards(site, thumbs):
    """Home: the first two "start here" videos large, then the rest of them, then the newest uploads."""
    top = featured(site)
    seen = {v["id"] for v in top}
    rest = [v for i, v in all_videos(site).items() if i not in seen and v["published"]]
    rest.sort(key=lambda v: v["published"], reverse=True)
    cards = (top + rest)[:HOME_CARDS]
    return "\n".join("      " + video_card(v, thumbs, " big" if k < 2 else "") for k, v in enumerate(cards))


def latest_section(site, thumbs):
    out = []
    top = featured(site)
    if top:
        out.append('  <h2 class="vsh">Start here</h2>\n  <div class="lvgrid two">\n'
                   + "\n".join("    " + video_card(v, thumbs, " lv", True) for v in top) + "\n  </div>")
    seen = {v["id"] for v in top}
    newest = [v for v in site["latest"] if v["id"] not in seen][:LATEST_ON_PAGE]
    if newest:
        vids = all_videos(site)
        out.append('  <h2 class="vsh">Latest videos</h2>\n  <div class="lvgrid">\n'
                   + "\n".join("    " + video_card(vids[v["id"]], thumbs, " lv", True) for v in newest) + "\n  </div>")
    if out:
        out.append('  <h2 class="vsh">Video guides</h2>')
    return "\n".join(out)


def video_articles(site):
    return "\n".join(f'    <article class="vid"><h3>{esc(v["title"])}</h3>{v["description_html"]}'
                     f'<a class="play" href="{attr(v["url"])}">Watch video</a></article>' for v in site["videos"])


def mascot(prefix, attrs, a11y, face="", neck=""):
    return fill((TPL / "partials/mascot.svg").read_text(encoding="utf-8"),
                {"p": prefix, "attrs": attrs, "a11y": a11y, "face": face, "neck": neck}, "mascot.svg")


# ---------------------------------------------------------------- assets
class Assets:
    """Copies files into dist/ with a content hash in the name, so they can be cached for a year."""

    def __init__(self):
        self.map = {}
        self.manifest = json.loads((SRC / "assets/manifest.json").read_text(encoding="utf-8"))

    def add(self, src, dest_dir):
        src = Path(src)
        data = src.read_bytes()
        h = hashlib.sha256(data).hexdigest()[:10]
        name = f"{src.stem}.{h}{src.suffix}"
        out = DIST / dest_dir / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return f"{dest_dir}/{name}"

    def size(self, rel):
        return self.manifest[rel]

    def asset(self, rel):
        """Copy src/assets/<rel> into dist/assets/ with a hashed name; return its URL."""
        if rel not in self.map:
            self.map[rel] = self.add(SRC / "assets" / rel, str(Path("assets") / Path(rel).parent))
        return self.map[rel]

    def picture(self, stem, fallback, alt, cls=None, extra=""):
        """<picture> with a WebP source, a JPEG/PNG fallback, and the image's real width and height."""
        w, h = self.size(f"{stem}.{fallback}")
        webp, img = self.asset(f"{stem}.webp"), self.asset(f"{stem}.{fallback}")
        c = f'class="{cls}" ' if cls else ""
        extra = f" {extra}" if extra else ""
        return (f'<picture><source srcset="{webp}" type="image/webp">'
                f'<img {c}src="{img}" alt="{attr(alt)}" width="{w}" height="{h}" decoding="async"{extra}></picture>')

    def add_text(self, text, dest_dir, stem, suffix):
        data = text.encode("utf-8")
        h = hashlib.sha256(data).hexdigest()[:10]
        out = DIST / dest_dir / f"{stem}.{h}{suffix}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return f"{dest_dir}/{stem}.{h}{suffix}"


# ---------------------------------------------------------------- main
def build():
    data, site = load()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    A = Assets()

    # logos: CSS background classes generated from the data (WebP with PNG fallback)
    logo_css = []
    for u in data["universities"]:
        stem = Path(u["logo"]).stem
        w, h = A.size(f"logos/{stem}.png")
        png, webp = A.asset(f"logos/{stem}.png"), A.asset(f"logos/{stem}.webp")
        logo_css.append(f".lg-{u['slug']}{{aspect-ratio:{w}/{h};background-image:url(../{png});"
                        f"background-image:image-set(url(../{webp}) type(\"image/webp\"),url(../{png}) type(\"image/png\"))}}")

    css = ((SRC / "css/fonts.css").read_text(encoding="utf-8") + "\n"
           + (SRC / "css/site.css").read_text(encoding="utf-8") + "\n"
           + "/* university logos (generated from data/programs.json) */\n" + "\n".join(logo_css) + "\n")
    fonts = {}
    for name in re.findall(r"url\(\.\./assets/fonts/([^)]+)\)", css):
        fonts[name] = A.asset(f"fonts/{name}")
    for name, url in fonts.items():
        css = css.replace(f"url(../assets/fonts/{name})", f"url(../{url})")
    css_url = A.add_text(css, "css", "site", ".css")
    js = (SRC / "js/site.js").read_text(encoding="utf-8")

    def thumbs(v):
        return A.picture(f"thumbs/{v['youtube_id']}", "jpg", alt="", extra='loading="lazy" onerror="this.remove()"')

    portrait = A.picture("photos/portrait", "jpg", alt="Portrait of Muhammad Aqib Khan in a navy suit", cls="me")
    contact_photo = A.picture(f"photos/{site['contact_photo']}", "jpg", alt="Muhammad Aqib Khan", cls="ava")

    n_courses = sum(1 for _ in all_programs(data))
    common = {
        "bank_note": esc(site["bank_note"]),
        "kuac_note": esc(site["kuac_note"]),
        "phone": esc(site["phone"]),
        "phone_tel": "+" + re.sub(r"\D", "", site["phone"]),
        "whatsapp": attr(site["whatsapp"]),
        "youtube": attr(site["socials"]["youtube"]["url"]),
    }
    pages = [
        tpl("home.html", **common,
            mascot_hero=mascot("", 'class="masc hm"',
                               'role="img" aria-label="A cute blue girl mascot with a pink hair bow waving hello"',
                               face=(TPL / "partials/mascot-bow.svg").read_text(encoding="utf-8")),
            n_unis=len(data["universities"]), n_courses=n_courses, intake=esc(data["intake"]),
            uni_tiles_home="".join(uni_tile(u) for u in data["universities"]),
            degree_tiles=degree_tiles(data), portrait=portrait,
            video_cards=video_cards(site, thumbs), socials_lite=socials(site, "lite")),
        tpl("universities.html", uni_tiles="".join(uni_tile(u) for u in data["universities"])),
        tpl("degrees.html", degree_tiles=degree_tiles(data)),
        tpl("courses.html", city_chips=city_chips(data), course_rows=course_rows(data)),
    ]
    for u in data["universities"]:
        pages.append(page_university(u))
        for lv in u["levels"]:
            pages.append(page_level(data, site, u, lv))
    for key, label in CATEGORIES:
        pages.append(page_degree(data, key, label))
    pages.append(tpl("videos.html", **common, video_buttons="".join(
        f'<a href="{attr(v["url"])}">{esc(v["title"])}</a>' for v in site["videos"]),
        latest_section=latest_section(site, thumbs),
        video_articles=video_articles(site)))
    pages.append((TPL / "basics.html").read_text(encoding="utf-8"))
    pages.append(tpl("about.html", **common, portrait=portrait))
    pages.append(tpl("contact.html", **common, contact_photo=contact_photo, socials_big=socials(site, "big")))

    # icons, sharing image and server files: fixed names at the site root (see tools/make_icons.py)
    for f in (SRC / "assets/meta").iterdir():
        shutil.copy(f, DIST / f.name)
    for f in (SRC / "root").iterdir():
        shutil.copy(f, DIST / f.name)
    (DIST / "site.webmanifest").write_text(json.dumps({
        "name": site["site_name"], "short_name": "Study In Korea", "start_url": "/", "display": "browser",
        "background_color": "#FFFFFF", "theme_color": "#0C324A",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]}, indent=2), encoding="utf-8")
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE_URL}</loc><lastmod>{datetime.date.today().isoformat()}</lastmod></url>\n</urlset>\n',
        encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    icon_links = ('<link rel="icon" href="/favicon.ico" sizes="32x32">\n'
                  '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
                  '<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
                  '<link rel="manifest" href="/site.webmanifest">')
    (DIST / "404.html").write_text(tpl("404.html", icon_links=icon_links, css_url=css_url), encoding="utf-8")

    head_links = f'<link rel="stylesheet" href="{css_url}">'
    page = tpl("layout.html", **common,
               site_url=SITE_URL, icon_links=icon_links,
               head_links=head_links,
               pages="\n".join(pages),
               mascot_pop=mascot("p", 'class="pmasc"', 'aria-hidden="true"',
                                 neck=(TPL / "partials/mascot-bowtie.svg").read_text(encoding="utf-8")),
               socials_footer=socials(site, "lite"),
               source=esc(data["source"]),
               script=js)
    # outside links open in a new tab (written into the HTML, so it works without the script)
    page = re.sub(r'<a ((?:class="[^"]*" )?href="https?://[^"]+")', r'<a \1 target="_blank" rel="noopener"', page)
    (DIST / "index.html").write_text(page, encoding="utf-8")
    print(f"Built dist/index.html: {len(pages)} page sections, {n_courses} courses, "
          f"{len(data['universities'])} universities.")


if __name__ == "__main__":
    build()
