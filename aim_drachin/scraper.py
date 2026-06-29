from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .config import ALLOWED_HOSTS, MAX_BYTES, MIN_REQUEST_INTERVAL, REQUEST_TIMEOUT


LAST_REQUEST_AT = 0.0


@dataclass
class PageData:
    title: str = ""
    description: str = ""
    canonical: str = ""
    headings: list[dict[str, str]] = field(default_factory=list)
    iframes: list[dict[str, str]] = field(default_factory=list)
    videos: list[dict[str, str]] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    scripts: list[dict[str, str]] = field(default_factory=list)
    meta: list[dict[str, str]] = field(default_factory=list)


class ScrapeParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.data = PageData()
        self._tag_stack: list[str] = []
        self._title_parts: list[str] = []
        self._heading_tag = ""
        self._heading_parts: list[str] = []
        self._current_link: dict[str, str] | None = None
        self._link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        self._tag_stack.append(tag)

        if tag in {"h1", "h2", "h3"}:
            self._heading_tag = tag
            self._heading_parts = []
        elif tag == "a" and attrs_map.get("href"):
            self._current_link = {
                "text": "",
                "href": self._absolute(attrs_map["href"]),
                "rel": attrs_map.get("rel", ""),
                "target": attrs_map.get("target", ""),
            }
            self._link_parts = []
        elif tag == "iframe" and attrs_map.get("src"):
            self.data.iframes.append(
                {
                    "src": self._absolute(attrs_map["src"]),
                    "title": attrs_map.get("title", ""),
                    "allow": attrs_map.get("allow", ""),
                }
            )
        elif tag == "video":
            self.data.videos.append(
                {
                    "src": self._absolute(attrs_map.get("src", "")),
                    "poster": self._absolute(attrs_map.get("poster", "")),
                    "controls": "controls" in attrs_map,
                }
            )
        elif tag == "source" and attrs_map.get("src"):
            self.data.sources.append(
                {
                    "src": self._absolute(attrs_map["src"]),
                    "type": attrs_map.get("type", ""),
                    "media": attrs_map.get("media", ""),
                }
            )
        elif tag == "img" and attrs_map.get("src"):
            self.data.images.append(
                {
                    "src": self._absolute(attrs_map["src"]),
                    "alt": attrs_map.get("alt", ""),
                    "width": attrs_map.get("width", ""),
                    "height": attrs_map.get("height", ""),
                    "loading": attrs_map.get("loading", ""),
                }
            )
        elif tag == "script":
            script_src = attrs_map.get("src", "")
            if script_src:
                self.data.scripts.append({"src": self._absolute(script_src), "type": attrs_map.get("type", "")})
        elif tag == "link":
            rel = attrs_map.get("rel", "")
            href = attrs_map.get("href", "")
            if "canonical" in rel and href:
                self.data.canonical = self._absolute(href)
        elif tag == "meta":
            name = attrs_map.get("name") or attrs_map.get("property") or attrs_map.get("itemprop")
            content = attrs_map.get("content", "")
            if name and content:
                record = {"name": name, "content": content}
                self.data.meta.append(record)
                if name.lower() in {"description", "og:description"} and not self.data.description:
                    self.data.description = content

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.data.title = _collapse(" ".join(self._title_parts))
            self._title_parts = []
        elif tag == self._heading_tag:
            text = _collapse(" ".join(self._heading_parts))
            if text:
                self.data.headings.append({"level": tag, "text": text})
            self._heading_tag = ""
            self._heading_parts = []
        elif tag == "a" and self._current_link:
            self._current_link["text"] = _collapse(" ".join(self._link_parts))
            self.data.links.append(self._current_link)
            self._current_link = None
            self._link_parts = []

        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, text: str) -> None:
        if not text.strip():
            return
        if self._tag_stack and self._tag_stack[-1] == "title":
            self._title_parts.append(text)
        if self._heading_tag:
            self._heading_parts.append(text)
        if self._current_link is not None:
            self._link_parts.append(text)

    def _absolute(self, value: str) -> str:
        if not value:
            return ""
        return urljoin(self.base_url, html.unescape(value.strip()))


def scrape(raw_url: str) -> dict[str, Any]:
    html_text, content_type, status = _fetch_url(raw_url)
    parser = ScrapeParser(raw_url)
    parser.feed(html_text)

    page = parser.data
    episodes = _extract_episodes(raw_url, page.links)
    cards = _extract_cards(raw_url, html_text, page.links)
    return {
        "url": raw_url,
        "status": status,
        "contentType": content_type,
        "title": page.title,
        "description": page.description,
        "canonical": page.canonical,
        "counts": {
            "headings": len(page.headings),
            "iframes": len(page.iframes),
            "videos": len(page.videos),
            "sources": len(page.sources),
            "images": len(page.images),
            "links": len(page.links),
            "scripts": len(page.scripts),
            "meta": len(page.meta),
            "episodes": len(episodes),
            "cards": len(cards),
        },
        "episodes": episodes,
        "cards": cards,
        "headings": page.headings[:80],
        "iframes": page.iframes[:80],
        "videos": page.videos[:80],
        "sources": page.sources[:120],
        "images": page.images[:120],
        "links": page.links[:180],
        "scripts": page.scripts[:100],
        "meta": page.meta[:120],
        "htmlBytes": len(html_text.encode("utf-8")),
    }


def _fetch_url(raw_url: str) -> tuple[str, str, int]:
    global LAST_REQUEST_AT

    if not _is_allowed_url(raw_url):
        raise ValueError("URL hanya boleh dari domain tv46.juragan.film atau juragan.film.")

    elapsed = time.monotonic() - LAST_REQUEST_AT
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)

    request = Request(
        raw_url,
        headers={
            "User-Agent": "aim-drachin-scraper/1.0 (+local educational scraper)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        LAST_REQUEST_AT = time.monotonic()
        status = getattr(response, "status", 200)
        content_type = response.headers.get("Content-Type", "")
        body = response.read(MAX_BYTES + 1)

    if len(body) > MAX_BYTES:
        raise ValueError("Respons terlalu besar untuk diproses.")

    encoding = "utf-8"
    match = re.search(r"charset=([\w.-]+)", content_type, re.IGNORECASE)
    if match:
        encoding = match.group(1)
    return body.decode(encoding, errors="replace"), content_type, status


def _is_allowed_url(raw_url: str) -> bool:
    parsed = urlparse(raw_url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in ALLOWED_HOSTS


def _episode_base_path(path: str) -> str:
    cleaned = path.rstrip("/")
    cleaned = re.sub(r"/\d+$", "", cleaned)
    return f"{cleaned}/"


def _extract_episodes(raw_url: str, links: list[dict[str, str]]) -> list[dict[str, Any]]:
    parsed_url = urlparse(raw_url)
    base_path = _episode_base_path(parsed_url.path)
    if "/film-seri/" not in base_path:
        return []

    current_match = re.search(r"/(\d+)/?$", parsed_url.path)
    current_episode = int(current_match.group(1)) if current_match else 1
    episodes: dict[int, str] = {1: urljoin(raw_url, base_path)}

    for link in links:
        text = link.get("text", "").strip()
        href = link.get("href", "")
        if not text.isdigit() or not href:
            continue

        episode_url = urlparse(href)
        if episode_url.hostname != parsed_url.hostname:
            continue
        if _episode_base_path(episode_url.path) != base_path:
            continue

        number = int(text)
        if 1 <= number <= 500:
            episodes[number] = href

    return [
        {"number": number, "url": episodes[number], "active": number == current_episode}
        for number in sorted(episodes)
    ]


def _extract_cards(raw_url: str, html_text: str, links: list[dict[str, str]]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in re.finditer(
        r'<div[^>]*class=["\'][^"\']*gmr-item-modulepost[^"\']*["\'][^>]*>(.*?)</div>\s*</div>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    ):
        block = match.group(1)
        image_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE | re.DOTALL)
        link_match = re.search(
            r"<a\b[^>]*rel=[\"'][^\"']*bookmark[^\"']*[\"'][^>]*>",
            block,
            re.IGNORECASE | re.DOTALL,
        )
        if not link_match:
            link_match = re.search(r"<a\b[^>]*itemprop=[\"']url[\"'][^>]*>", block, re.IGNORECASE | re.DOTALL)
        if not link_match:
            continue

        href = urljoin(raw_url, _attr(link_match.group(0), "href"))
        if not href or href in seen:
            continue

        image = ""
        alt = ""
        title = _attr(link_match.group(0), "title")
        heading_match = re.search(
            r'<h2\b[^>]*class=["\'][^"\']*entry-title[^"\']*["\'][^>]*>(.*?)</h2>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        if heading_match:
            title = _strip_tags(heading_match.group(1)) or title

        if image_match:
            image_tag = image_match.group(0)
            image = urljoin(raw_url, _attr(image_tag, "src"))
            alt = _attr(image_tag, "alt")
            title = title or _attr(image_tag, "title") or alt

        quality_match = re.search(
            r'<div[^>]*class=["\'][^"\']*gmr-quality-item[^"\']*["\'][^>]*>(.*?)</div>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        rating_match = re.search(
            r'<div[^>]*class=["\'][^"\']*gmr-rating-item[^"\']*["\'][^>]*>(.*?)</div>',
            block,
            re.IGNORECASE | re.DOTALL,
        )
        episode_match = re.search(
            r'<div[^>]*class=["\'][^"\']*strokeepisode[^"\']*["\'][^>]*>(.*?)</div>',
            block,
            re.IGNORECASE | re.DOTALL,
        )

        cards.append(
            {
                "title": title or alt or href,
                "url": href,
                "image": image,
                "alt": alt,
                "quality": _strip_tags(quality_match.group(1)) if quality_match else "",
                "rating": _strip_tags(rating_match.group(1)).replace("★", "").strip() if rating_match else "",
                "episode": _strip_tags(episode_match.group(1)) if episode_match else "",
            }
        )
        seen.add(href)

    if cards:
        return cards[:120]

    for link in links:
        href = link.get("href", "")
        text = link.get("text", "")
        rel = link.get("rel", "")
        if "bookmark" not in rel or not href or href in seen or not text:
            continue
        cards.append({"title": text, "url": href, "image": "", "alt": "", "quality": "", "rating": "", "episode": ""})
        seen.add(href)

    return cards[:120]


def _attr(markup: str, name: str) -> str:
    match = re.search(rf"""\s{name}\s*=\s*(['"])(.*?)\1""", markup, re.IGNORECASE | re.DOTALL)
    return html.unescape(match.group(2)).strip() if match else ""


def _strip_tags(value: str) -> str:
    return _collapse(re.sub(r"<[^>]+>", " ", html.unescape(value)))


def _collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
