"""
Website cloner for vgagrentalbikes.in
Downloads HTML pages and all linked assets (CSS, JS, images, fonts)
preserving the site structure for local browsing.
"""

import os
import re
import time
import urllib.parse
from collections import deque
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://vgagrentalbikes.in"
OUTPUT_DIR = Path("vgagrentalbikes_clone")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

ASSET_TAGS = {
    "link":   ["href"],
    "script": ["src"],
    "img":    ["src", "data-src", "data-lazy-src"],
    "source": ["src", "srcset"],
    "video":  ["src"],
    "audio":  ["src"],
}

visited_pages: set[str] = set()
downloaded_assets: set[str] = set()
session = requests.Session()
session.headers.update(HEADERS)


def normalize(url: str, base: str = BASE_URL) -> str | None:
    """Resolve a URL against base and return None if it's off-domain or unusable."""
    if not url or url.startswith(("data:", "mailto:", "tel:", "javascript:", "#")):
        return None
    full = urllib.parse.urljoin(base, url.split("?")[0].split("#")[0])
    parsed = urllib.parse.urlparse(full)
    if parsed.netloc and parsed.netloc not in urllib.parse.urlparse(BASE_URL).netloc:
        return None
    return full


def local_path(url: str) -> Path:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lstrip("/") or "index.html"
    # Bare directories get index.html
    if not Path(path).suffix or path.endswith("/"):
        path = path.rstrip("/") + "/index.html" if "/" in path else "index.html"
    return OUTPUT_DIR / path


def canonical_page_url(url: str) -> str:
    """Normalise page URLs so we never have duplicate /index.html vs / entries."""
    return url.removesuffix("/index.html").rstrip("/") + "/"


def save(url: str, content: bytes) -> Path:
    dest = local_path(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest


def fetch(url: str) -> requests.Response | None:
    try:
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [SKIP] {url}  →  {e}")
        return None


def download_asset(url: str) -> None:
    if url in downloaded_assets:
        return
    downloaded_assets.add(url)
    r = fetch(url)
    if r:
        save(url, r.content)
        print(f"  [asset] {url}")


def extract_srcset_urls(srcset: str) -> list[str]:
    """Parse a srcset attribute and return the raw URLs."""
    urls = []
    for part in srcset.split(","):
        token = part.strip().split()[0]
        if token:
            urls.append(token)
    return urls


def extract_css_urls(css_text: str, base_url: str) -> list[str]:
    """Find url(...) references inside CSS content."""
    found = re.findall(r'url\(["\']?([^)"\']+)["\']?\)', css_text)
    result = []
    for u in found:
        n = normalize(u, base_url)
        if n:
            result.append(n)
    return result


def server_url(url: str) -> str:
    """Return the actual server URL (strip any /index.html we may have added)."""
    return url.removesuffix("/index.html").removesuffix("index.html") or url


def crawl_page(url: str) -> list[str]:
    """Download one HTML page, save it, download its assets, return child page URLs."""
    if url in visited_pages:
        return []
    visited_pages.add(url)
    fetch_url = server_url(url)

    print(f"[page] {fetch_url}")
    r = fetch(fetch_url)
    if not r:
        return []

    content_type = r.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        # Treat as asset
        save(url, r.content)
        return []

    soup = BeautifulSoup(r.content, "lxml")

    # ── Collect asset URLs ────────────────────────────────────────────────────
    asset_urls: list[str] = []
    for tag, attrs in ASSET_TAGS.items():
        for element in soup.find_all(tag):
            for attr in attrs:
                val = element.get(attr, "")
                if not val:
                    continue
                if attr == "srcset":
                    for u in extract_srcset_urls(val):
                        n = normalize(u, url)
                        if n:
                            asset_urls.append(n)
                else:
                    n = normalize(val, url)
                    if n:
                        asset_urls.append(n)

    for asset_url in asset_urls:
        download_asset(asset_url)
        # If it's a CSS file, also chase its url() references
        if asset_url.endswith(".css"):
            r_css = fetch(asset_url)
            if r_css:
                for sub in extract_css_urls(r_css.text, asset_url):
                    download_asset(sub)

    # ── Rewrite links to be relative (so the clone works offline) ────────────
    for tag, attrs in ASSET_TAGS.items():
        for element in soup.find_all(tag):
            for attr in attrs:
                val = element.get(attr, "")
                if not val:
                    continue
                n = normalize(val, url)
                if n:
                    rel = os.path.relpath(local_path(n), local_path(url).parent)
                    element[attr] = rel.replace("\\", "/")

    for a in soup.find_all("a", href=True):
        n = normalize(a["href"], url)
        if n:
            rel = os.path.relpath(local_path(n), local_path(url).parent)
            a["href"] = rel.replace("\\", "/")

    # Save rewritten HTML
    save(url, soup.encode())

    # ── Collect child page URLs ───────────────────────────────────────────────
    child_pages: list[str] = []
    for a in soup.find_all("a", href=True):
        n = normalize(a["href"], url)
        if n:
            n = canonical_page_url(n)
            if n not in visited_pages:
                child_pages.append(n)

    return child_pages


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Cloning {BASE_URL}  ->  {OUTPUT_DIR.resolve()}\n")

    queue: deque[str] = deque([canonical_page_url(BASE_URL)])
    while queue:
        page_url = queue.popleft()
        children = crawl_page(page_url)
        for child in children:
            if child not in visited_pages:
                queue.append(child)
        time.sleep(0.3)   # be polite — don't hammer the server

    print(f"\nDone. Pages: {len(visited_pages)}, Assets: {len(downloaded_assets)}")
    print(f"Output: {OUTPUT_DIR.resolve()}")
    print(f"Open:   {(OUTPUT_DIR / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
