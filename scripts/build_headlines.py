import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "headlines.json"
TIMEOUT = 12

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
        "id": "reuters_world",
        "name": "Reuters World",
        "site_url": "https://www.reuters.com/world/",
        "feed_url": "https://www.reutersagency.com/feed/?best-topics=world&post_type=best",
        "terms_url": "https://www.reuters.com/info-pages/terms-of-use/"
    },
    {
        "id": "cnn_world",
        "name": "CNN World",
        "site_url": "https://edition.cnn.com/world",
        "feed_url": "https://rss.cnn.com/rss/edition_world.rss",
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

IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


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


def fetch_feed(feed_url: str) -> str:
    req = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "AggNewsStaticBuilder/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8"
        }
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
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


def parse_headlines(xml_text: str, limit: int):
    root = ET.fromstring(xml_text)
    items = [elem for elem in root.iter() if localname(elem.tag) == "item"]
    if not items:
        items = [elem for elem in root.iter() if localname(elem.tag) == "entry"]

    results = []
    for node in items[:limit]:
        results.append(
            {
                "title": text_of(node, {"title"}) or "(no title)",
                "translated_title": "",
                "link": pick_link(node),
                "published_at": text_of(node, {"pubDate", "published", "updated"}),
                "image_url": pick_image(node)
            }
        )

    return results


def build_payload(limit: int = 8) -> dict:
    sources = []
    for source in SOURCES:
        row = {
            "id": source["id"],
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
            row["headlines"] = parse_headlines(xml_text, limit)
        except (ET.ParseError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            row["error"] = str(exc)
        except Exception as exc:
            row["error"] = f"unexpected: {exc}"
        sources.append(row)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(sources),
        "limit": limit,
        "translation": "disabled",
        "mode": "static-json",
        "sources": sources
    }


def main():
    payload = build_payload(limit=8)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for s in payload["sources"] if not s["error"])
    print(f"Wrote {OUTPUT_PATH} ({ok}/{payload['source_count']} sources OK)")


if __name__ == "__main__":
    main()


