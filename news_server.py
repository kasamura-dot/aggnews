import json
import os
import gzip
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000
CACHE_TTL_SEC = 600
REQUEST_TIMEOUT_SEC = 12
MAX_WORKERS = 8

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
DEEPL_API_URL = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate").strip()

SOURCES = [
    {
        "id": "nhk",
        "name": "NHK",
        "site_url": "https://www3.nhk.or.jp/news/",
        "feed_url": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "terms_url": "https://www.nhk.or.jp/rules/"
    },
    {
        "id": "bbc_world",
        "name": "BBC World",
        "site_url": "https://www.bbc.com/news/world",
        "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "terms_url": "https://www.bbc.com/usingthebbc/terms"
    },
    {
        "id": "cbs_world",
        "name": "CBS World",
        "site_url": "https://www.cbsnews.com/world/",
        "feed_url": "https://www.cbsnews.com/latest/rss/world",
        "terms_url": "https://www.paramount.com/legal/us/en/cbsi/terms-of-use"
    },
    {
        "id": "cnn_world",
        "name": "CNN World",
        "site_url": "https://edition.cnn.com/world",
        "feed_url": "http://rss.cnn.com/rss/edition_world.rss",
        "terms_url": "https://www.cnn.com/terms"
    },
    {
        "id": "nytimes_world",
        "name": "NYTimes World",
        "site_url": "https://www.nytimes.com/section/world",
        "feed_url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "terms_url": "https://help.nytimes.com/hc/en-us/articles/115014893428-Terms-of-service"
    },
    {
        "id": "guardian_world",
        "name": "The Guardian World",
        "site_url": "https://www.theguardian.com/world",
        "feed_url": "https://www.theguardian.com/world/rss",
        "terms_url": "https://www.theguardian.com/help/terms-of-service"
    },
    {
        "id": "aljazeera",
        "name": "Al Jazeera",
        "site_url": "https://www.aljazeera.com/",
        "feed_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "terms_url": "https://www.aljazeera.com/terms-and-conditions"
    },
    {
        "id": "un_news",
        "name": "UN News",
        "site_url": "https://news.un.org/",
        "feed_url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        "terms_url": "https://www.un.org/en/about-us/terms-of-use"
    },
    {
        "id": "npr",
        "name": "NPR",
        "site_url": "https://www.npr.org/",
        "feed_url": "https://feeds.npr.org/1001/rss.xml",
        "terms_url": "https://www.npr.org/about-npr/179876898/terms-of-use"
    },
    {
        "id": "dw",
        "name": "DW",
        "site_url": "https://www.dw.com/en/top-stories/s-9097",
        "feed_url": "https://rss.dw.com/xml/rss-en-all",
        "terms_url": "https://www.dw.com/en/legal-notice/a-2094"
    },
    {
        "id": "france24",
        "name": "France 24",
        "site_url": "https://www.france24.com/en/",
        "feed_url": "https://www.france24.com/en/rss",
        "terms_url": "https://www.france24.com/en/terms-and-conditions/"
    }
]

CACHE = {}
TRANSLATION_CACHE = {}
IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)
JP_RE = re.compile(r"[ぁ-んァ-ヶ一-龠]")
EN_RE = re.compile(r"[A-Za-z]")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def localname(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def text_of(parent, names):
    for elem in parent.iter():
        if localname(elem.tag) in names:
            value = (elem.text or "").strip()
            if value:
                return value
    return ""


def pick_link(node) -> str:
    for elem in node.iter():
        if localname(elem.tag) == "link":
            href = (elem.attrib.get("href") or "").strip()
            if href:
                return href
            value = (elem.text or "").strip()
            if value:
                return value
    return ""


def pick_image(node) -> str:
    for elem in node.iter():
        lname = localname(elem.tag)
        if lname in ("thumbnail", "content"):
            url = (elem.attrib.get("url") or elem.attrib.get("href") or "").strip()
            if url:
                return url
        if lname == "enclosure":
            content_type = (elem.attrib.get("type") or "").lower()
            url = (elem.attrib.get("url") or "").strip()
            if url and content_type.startswith("image/"):
                return url

    html_blob = text_of(node, {"description", "encoded", "content"})
    if html_blob:
        match = IMG_RE.search(html_blob)
        if match:
            return match.group(1)

    return ""


def parse_feed(xml_text: str, limit: int):
    root = ET.fromstring(xml_text)

    items = [elem for elem in root.iter() if localname(elem.tag) == "item"]
    if not items:
        items = [elem for elem in root.iter() if localname(elem.tag) == "entry"]

    headlines = []
    for node in items[:limit]:
        title = text_of(node, {"title"}) or "(no title)"
        link = pick_link(node)
        published = text_of(node, {"pubDate", "published", "updated"})
        image_url = pick_image(node)

        headlines.append(
            {
                "title": title,
                "translated_title": "",
                "link": link,
                "published_at": published,
                "image_url": image_url
            }
        )

    return headlines


def seems_english(text: str) -> bool:
    if not text:
        return False
    if JP_RE.search(text):
        return False
    return len(EN_RE.findall(text)) >= 6


def translate_title(text: str) -> str:
    if not DEEPL_API_KEY:
        return ""
    if not seems_english(text):
        return ""

    cached = TRANSLATION_CACHE.get(text)
    if cached is not None:
        return cached

    payload = urllib.parse.urlencode(
        {
            "auth_key": DEEPL_API_KEY,
            "text": text,
            "target_lang": "JA"
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        DEEPL_API_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            translated = (data.get("translations") or [{}])[0].get("text", "").strip()
            TRANSLATION_CACHE[text] = translated
            return translated
    except Exception:
        return ""


def fetch_feed(feed_url: str) -> str:
    req = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "AggNews/1.0 (+https://localhost; headlines-links-only)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8"
        }
    )

    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
        raw = resp.read()
        if raw.startswith(b"\x1f\x8b"):
            raw = gzip.decompress(raw)
        candidates = ["utf-8", "utf-8-sig"]

        header_charset = resp.headers.get_content_charset()
        if header_charset:
            candidates.append(header_charset)

        xml_decl = re.search(rb"encoding=[\"']([A-Za-z0-9_\-]+)[\"']", raw[:200], re.IGNORECASE)
        if xml_decl:
            decl_charset = xml_decl.group(1).decode("ascii", errors="ignore")
            if decl_charset:
                candidates.append(decl_charset)

        candidates.extend(["cp932", "shift_jis", "euc-jp", "iso-2022-jp", "latin-1"])

        used = set()
        for enc in candidates:
            key = enc.lower()
            if key in used:
                continue
            used.add(key)
            try:
                return raw.decode(enc)
            except (LookupError, UnicodeDecodeError):
                continue

        return raw.decode("utf-8", errors="replace")


def get_source_result(source: dict, limit: int) -> dict:
    source_id = source["id"]
    cache_entry = CACHE.get(source_id)
    now = time.time()

    if cache_entry and now - cache_entry["fetched_epoch"] <= CACHE_TTL_SEC:
        return {
            **cache_entry["payload"],
            "from_cache": True
        }

    base = {
        "id": source_id,
        "name": source["name"],
        "site_url": source["site_url"],
        "feed_url": source["feed_url"],
        "terms_url": source["terms_url"],
        "headlines": [],
        "error": "",
        "from_cache": False
    }

    try:
        xml_text = fetch_feed(source["feed_url"])
        headlines = parse_feed(xml_text, limit)
        for item in headlines:
            item["translated_title"] = translate_title(item["title"])

        payload = {
            **base,
            "headlines": headlines
        }
    except (ET.ParseError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        payload = {
            **base,
            "error": str(exc)
        }
    except Exception as exc:
        payload = {
            **base,
            "error": f"unexpected: {exc}"
        }

    CACHE[source_id] = {
        "fetched_epoch": now,
        "payload": payload
    }

    return payload


def build_payload(limit: int) -> dict:
    results = []
    max_workers = min(MAX_WORKERS, len(SOURCES))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_source_result, source, limit): source for source in SOURCES}
        for future in as_completed(futures):
            results.append(future.result())

    source_order = {source["id"]: idx for idx, source in enumerate(SOURCES)}
    results.sort(key=lambda item: source_order.get(item["id"], 9999))

    return {
        "fetched_at": now_utc_iso(),
        "source_count": len(SOURCES),
        "limit": limit,
        "translation": "deepl" if DEEPL_API_KEY else "disabled",
        "sources": results
    }


class AggNewsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).resolve().parent), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/headlines":
            self.handle_headlines_api(parsed)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        return

    def do_OPTIONS(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/headlines":
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        super().do_OPTIONS()

    def handle_headlines_api(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        try:
            limit = int((query.get("limit") or ["8"])[0])
        except ValueError:
            limit = 8
        limit = max(1, min(limit, 20))

        payload = build_payload(limit)
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    print(f"AggNews server listening on http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    with ThreadingHTTPServer((HOST, PORT), AggNewsHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()






