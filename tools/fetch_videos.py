"""Add new YouTube uploads to data/latest_videos.json, cleaned for the website.

    python3 tools/fetch_videos.py            # fetch, clean, save, download thumbnails
    python3 tools/fetch_videos.py --dry-run  # show what would be added, change nothing

Runs every night on GitHub (.github/workflows/nightly-videos.yml) and can be run by hand.
No key or password is needed: it reads the channel's public feed, or its public pages
if the feed is down. Videos already in data/site.json (the hand-written ones) are skipped.

Cleaning, as the owner asked (2026-11-16):
- titles: a plain headline, no hashtags and no sales lines (owner, 2026-11-16). Only the
  first part of the YouTube title is kept, up to the first "|" or long dash (—); the rest is usually
  a hook or a sales line ("| Study in Korea with Zero Consultation Fee"). A hashtag inside
  the headline becomes a plain word ("for #pakistani Students" -> "for Pakistani Students").
  Emoji are removed.
- the owner can set his own headline for any video: "overrides" in data/latest_videos.json,
  {"<video id>": "<headline>"}. It always wins and is never overwritten.
- Shorts cut from a long video are not shown (owner, 2026-11-17). A Short counts as a clip
  when its description links one of the channel's long videos (youtu.be/<id> or
  watch?v=<id>). Any other video can be hidden by hand: "hidden" in data/latest_videos.json,
  a list of video ids.
- thumbnails are checked every run; a cover changed on YouTube replaces the old one,
  for the hand-written videos too.
- descriptions: only the opening paragraph, cut to a short summary of whole sentences.
  No links, hashtags, phone numbers, email addresses or emoji.
"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data/latest_videos.json"
THUMBS = ROOT / "src/assets/thumbs"
MANIFEST = ROOT / "src/assets/manifest.json"
CHANNEL_ID = "UCewrC3Pg5vXtmM95L6z0j5w"
HANDLE = "aqibinkorea"
SUMMARY_MAX = 280
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1; SOCS=CAI"}

EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️‍⭐⬆↔-⇿]")
URL = re.compile(r"(https?://\S+|www\.\S+|\b[\w.-]+\.(?:com|net|org|pk|kr|io|me|ly)(?:/\S*)?)", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
HASHTAG = re.compile(r"#[\w]+", re.U)
CONTACT_WORDS = re.compile(r"\b(whats\s?app|contact|call|email|e-mail|subscribe|follow me|instagram|tiktok|facebook|website)\b", re.I)


def korea_date(stamp):
    """YouTube gives times in UTC or US time; the site shows the date in Korea."""
    import datetime
    try:
        t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return t.astimezone(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat() if t.tzinfo else stamp[:10]
    except ValueError:
        return stamp[:10]


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


# ---------------------------------------------------------------- cleaning

def tidy(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    return s.strip(" |-—–:;,")


def clean_title(raw):
    t = EMOJI.sub("", html.unescape(raw))
    parts = []
    for seg in re.split(r"\s*\|\s*|\s+[—–]\s+", t):
        # hashtags at the end of a part are tags, not words: drop them
        seg = re.sub(r"(\s*#\w+)+\s*$", "", seg)
        # a hashtag inside a sentence is a word: keep it, without the #
        seg = HASHTAG.sub(lambda m: m.group(0)[1:2].upper() + m.group(0)[2:], seg)
        seg = tidy(seg)
        if len(seg.split()) >= 2:
            parts.append(seg)
    return parts[0] if parts else ""


def clean_description(raw):
    text = EMOJI.sub("", html.unescape(raw or "")).replace("\r", "")
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    for p in paras:
        lines = []
        for line in p.split("\n"):
            if URL.search(line) or EMAIL.search(line) or PHONE.search(line) or CONTACT_WORDS.search(line):
                continue
            line = HASHTAG.sub("", line)
            if tidy(line):
                lines.append(tidy(line))
        para = tidy(" ".join(lines))
        if len(para.split()) >= 6:
            return summary(para)
    return ""


def summary(para):
    sentences = re.findall(r"[^.!?]+[.!?]+(?:[\"'’”)]+)?|[^.!?]+$", para)
    out = ""
    for s in sentences:
        s = s.strip()
        if not out:
            out = s
        elif len(out) + 1 + len(s) <= SUMMARY_MAX:
            out += " " + s
        else:
            break
    if len(out) > SUMMARY_MAX + 60:  # one very long sentence: cut at a word
        out = out[:SUMMARY_MAX].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return out


# ---------------------------------------------------------------- reading YouTube

def from_feed():
    """The channel's public Atom feed: newest 15 uploads with full descriptions."""
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    import time
    urls = [f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}",
            f"https://www.youtube.com/feeds/videos.xml?playlist_id=UU{CHANNEL_ID[2:]}"]
    for attempt in range(4):  # the feed is often down for a moment: try a few times
        try:
            root = ET.fromstring(get(urls[attempt % 2]))
            break
        except Exception as err:
            print(f"  feed try {attempt + 1}: {err}")
            if attempt == 3:
                raise
            time.sleep(20)
    out = []
    for e in root.findall("a:entry", ns):
        out.append({"id": e.find("yt:videoId", ns).text,
                    "url": e.find("a:link", ns).get("href"),
                    "title_raw": e.find("a:title", ns).text or "",
                    "description_raw": e.find("m:group/m:description", ns).text or "",
                    "published": korea_date(e.find("a:published", ns).text or "")})
    return out


def ids_from_pages():
    """Video ids from the channel's Videos and Shorts tabs, as fallback when the feed is down."""
    found = []
    for tab, kind in (("videos", "watch"), ("shorts", "shorts")):
        page = get(f"https://www.youtube.com/@{HANDLE}/{tab}").decode("utf-8", "replace")
        pat = r'"reelWatchEndpoint":\{"videoId":"([\w-]{11})"' if kind == "shorts" else r'"videoId":"([\w-]{11})"'
        ids = list(dict.fromkeys(re.findall(pat, page)))
        print(f"  channel {tab}: {len(ids)} videos found")
        found += [(vid, kind) for vid in ids]
    if not found:
        raise RuntimeError("no videos found on the channel pages (YouTube may have blocked the request)")
    return found


def from_watch_page(vid, kind):
    page = get(f"https://www.youtube.com/watch?v={vid}").decode("utf-8", "replace")
    m = re.search(r"var ytInitialPlayerResponse = (\{.*?\});(?:var |</script>)", page)
    p = json.loads(m.group(1))
    d = p["videoDetails"]
    if d.get("channelId") != CHANNEL_ID:
        return None
    mf = p.get("microformat", {}).get("playerMicroformatRenderer", {})
    url = f"https://youtube.com/shorts/{vid}" if kind == "shorts" else f"https://youtu.be/{vid}"
    return {"id": vid, "url": url, "title_raw": d.get("title", ""),
            "description_raw": d.get("shortDescription", ""),
            "published": korea_date(mf.get("publishDate") or mf.get("uploadDate") or "")}


def from_oembed(vid, kind):
    """Title only, from YouTube's public oEmbed endpoint, which servers can usually still read.
    The description and exact date come later, on a night when the feed answers."""
    url = f"https://youtube.com/shorts/{vid}" if kind == "shorts" else f"https://youtu.be/{vid}"
    d = json.loads(get(f"https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v={vid}"))
    if "youtube.com/channel/" + CHANNEL_ID not in d.get("author_url", "") and HANDLE not in d.get("author_url", "").lower():
        return None
    import datetime
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
    return {"id": vid, "url": url, "title_raw": d.get("title", ""), "description_raw": "",
            "published": today, "pending": True}


def thumbnail(vid, sources):
    """Save hqdefault (480 x 360) as JPEG and WebP, and record its size, like tools/prepare_assets.py.
    Checked every run: when the owner changes a cover on YouTube, the new one replaces the old.
    `sources` remembers a fingerprint of each downloaded cover, so unchanged ones are left alone."""
    import hashlib
    jpg, webp = THUMBS / f"{vid}.jpg", THUMBS / f"{vid}.webp"
    try:
        raw = get(f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")
    except Exception as err:  # not reachable now: keep the saved one, try again next run
        print(f"  thumbnail for {vid} not checked: {err}")
        return jpg.exists() and webp.exists()
    mark = hashlib.sha256(raw).hexdigest()[:16]
    if sources.get(vid) == mark and jpg.exists() and webp.exists():
        return True
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as err:  # Pillow missing: try again next run
        print(f"  thumbnail for {vid} not saved: {err}")
        return jpg.exists() and webp.exists()
    print(f"  thumbnail {'new' if vid not in sources else 'updated'}: {vid}")
    im.save(jpg, "JPEG", quality=82, optimize=True, progressive=True)
    im.save(webp, "WEBP", quality=78, method=6)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for f in (jpg, webp):
        man[f"thumbs/{f.name}"] = list(im.size)
    MANIFEST.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sources[vid] = mark
    return True


def clip_of(v, long_ids):
    """A Short cut from a long video says so by linking that video in its description
    ("In the full video ... youtu.be/<id>"). Such clips are not shown on the website (owner,
    2026-11-17): the long video is shown instead. Returns the long video's id, or None."""
    if "/shorts/" not in v["url"]:
        return None
    for vid in re.findall(r"(?:youtu\.be/|watch\?v=|/live/)([\w-]{11})", v.get("youtube_description", "")):
        if vid != v["id"] and vid in long_ids:
            return vid
    return None


# ---------------------------------------------------------------- main

def main(dry_run=False):
    site = json.loads((ROOT / "data/site.json").read_text(encoding="utf-8"))
    hand_written = {v["youtube_id"] for v in site["videos"]}
    store = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"videos": []}
    store.setdefault("overrides", {})
    known = {v["id"]: v for v in store["videos"]}

    try:
        items = from_feed()
        print(f"Feed: {len(items)} videos")
    except Exception as err:
        print(f"Feed not available ({err}); reading the channel pages instead")
        items = []
        for vid, kind in ids_from_pages():
            old = known.get(vid)
            if vid in hand_written or (old and old.get("youtube_title") and not old.get("pending")):
                continue
            try:
                v = from_watch_page(vid, kind)
            except Exception as err2:
                print(f"  {vid}: video page not readable ({err2})")
                v = None
                if not old:  # new video: show it now with its title, details follow later
                    try:
                        v = from_oembed(vid, kind)
                    except Exception as err3:
                        print(f"  {vid}: title not readable either ({err3}); trying again next run")
            if v:
                items.append(v)
        print(f"Channel pages: {len(items)} videos to check")

    added = updated = 0
    for it in items:
        if it["id"] in hand_written:
            continue
        v = {"id": it["id"], "url": it["url"], "published": it["published"],
             "youtube_title": it["title_raw"], "youtube_description": it["description_raw"]}
        if it.get("pending"):
            v["pending"] = True  # description and exact date still to come
        old = known.get(v["id"])
        fields = ("url", "published", "youtube_title", "youtube_description", "pending")
        if old and all(old.get(k) == v.get(k) for k in fields):
            continue
        print(("  update " if old else "  new    ") + f'{v["published"]}  {clean_title(v["youtube_title"])}')
        known[v["id"]] = v
        added += old is None
        updated += old is not None

    if dry_run:
        print(f"Dry run: {added} new, {updated} updated. Nothing saved.")
        return
    sources = store.get("thumbnail_sources", {})
    for vid in sorted(hand_written):  # covers of the hand-written videos stay current too
        thumbnail(vid, sources)
    for vid in list(known):
        if not thumbnail(vid, sources):
            known.pop(vid)  # no thumbnail yet: leave it for the next run
    long_ids = {vid for vid, v in known.items() if "/shorts/" not in v["url"]}
    long_ids |= {v["youtube_id"] for v in site["videos"] if "/shorts/" not in v.get("url", "")}
    for v in known.values():  # clean every video with the current rules
        v["title"] = clean_title(v.get("youtube_title", v.get("title", "")))
        v["title"] = v["title"] or tidy(HASHTAG.sub("", EMOJI.sub("", v.get("youtube_title", ""))))
        v["description"] = clean_description(v.get("youtube_description", ""))
        v.pop("clip_of", None)
        if clip_of(v, long_ids):
            v["clip_of"] = clip_of(v, long_ids)  # hidden on the website
    store = {"overrides": store["overrides"], "hidden": store.get("hidden", []),
             "thumbnail_sources": dict(sorted(sources.items()))}
    store["videos"] = sorted(known.values(), key=lambda v: (v["published"], v["id"]), reverse=True)
    DATA.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved: {added} new, {updated} updated, {len(store['videos'])} in total.")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
