"""
Padma Impex Photo Downloader
Scans https://padmaimpex.com and downloads all product photos.

Usage:
    python download_padmaimpex_photos.py

Photos are saved to ./padmaimpex_photos/
"""
import sys
import io

# Force UTF-8 output so progress ticks print correctly on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import re
import time
import hashlib
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ── Configuration ────────────────────────────────────────────────────────────
BASE_URL       = "https://padmaimpex.com"
SITEMAP_URL    = "https://padmaimpex.com/sitemap.xml"
OUTPUT_DIR     = "padmaimpex_photos"
DELAY_SECONDS  = 0.3   # polite delay between page requests
MAX_WORKERS    = 6     # parallel image downloads
TIMEOUT        = 20    # request timeout in seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# CDN host that serves all product images
CDN_HOST = "d1311wbk6unapo.cloudfront.net"

# Regex: find every CDN URL in raw HTML (covers img src, og:image, preload hrefs, JS strings)
CDN_URL_RE = re.compile(
    r'https?://' + re.escape(CDN_HOST) + r'/[^\s"\'<>)]+',
    re.IGNORECASE,
)

# Only keep catalogue / product images; skip icons, favicons, placeholders, JS assets
SKIP_PATTERNS = re.compile(
    r'(favicon|placeholder|NushopWebsiteAsset.*\.(js|css)|\.woff|\.ttf|\.svg)',
    re.IGNORECASE,
)

session = requests.Session()
session.headers.update(HEADERS)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_html(url: str) -> str | None:
    try:
        r = session.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  [WARN] Could not fetch {url}: {e}")
        return None


def parse_sitemap(xml_text: str) -> list[str]:
    """Return all <loc> URLs from a sitemap."""
    soup = BeautifulSoup(xml_text, "lxml-xml")
    return [loc.get_text(strip=True) for loc in soup.find_all("loc")]


def extract_image_urls(html: str) -> set[str]:
    """Pull every CDN image URL from raw HTML."""
    found = set()
    for url in CDN_URL_RE.findall(html):
        # strip trailing punctuation that crept in
        url = url.rstrip('",;)')
        if SKIP_PATTERNS.search(url):
            continue
        # Normalise: remove ImageKit transform parameters so we get full-res originals.
        # Pattern: /tr:.../ between the host path prefix and the actual file path.
        clean = re.sub(r'/tr:[^/]+/', '/', url)
        found.add(clean)
    return found


def url_to_filename(url: str) -> str:
    """
    Turn a CDN URL into a clean local filename.
    Keep the last meaningful path segment plus a short hash to avoid collisions.
    """
    parsed = urllib.parse.urlparse(url)
    basename = os.path.basename(parsed.path)
    # Some URLs have query strings; strip them from the extension guess
    basename = basename.split("?")[0] or "image"
    short_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    name, ext = os.path.splitext(basename)
    ext = ext or ".jpg"
    return f"{name}_{short_hash}{ext}"


def download_image(url: str, dest_dir: str) -> tuple[str, bool]:
    """Download one image. Returns (url, success)."""
    filename = url_to_filename(url)
    filepath = os.path.join(dest_dir, filename)
    if os.path.exists(filepath):
        return url, True  # already downloaded

    try:
        r = session.get(url, timeout=TIMEOUT, stream=True)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        if "image" not in content_type and "octet-stream" not in content_type:
            return url, False
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return url, True
    except Exception as e:
        print(f"  [WARN] Failed to download {url}: {e}")
        return url, False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Fetch sitemap
    print("Fetching sitemap …")
    xml = fetch_html(SITEMAP_URL)
    if not xml:
        print("ERROR: Could not fetch sitemap. Aborting.")
        return

    page_urls = parse_sitemap(xml)
    # Also include the homepage
    page_urls = list({BASE_URL, *page_urls})
    print(f"Found {len(page_urls)} URLs in sitemap.")

    # 2. Crawl each page and collect image URLs
    all_image_urls: set[str] = set()

    for i, url in enumerate(page_urls, 1):
        print(f"[{i}/{len(page_urls)}] Scanning {url}")
        html = fetch_html(url)
        if html:
            imgs = extract_image_urls(html)
            print(f"         Found {len(imgs)} image(s)")
            all_image_urls.update(imgs)
        time.sleep(DELAY_SECONDS)

    print(f"\nTotal unique images collected: {len(all_image_urls)}")

    # 3. Download all images in parallel
    print(f"Downloading to ./{OUTPUT_DIR}/ …\n")
    success = 0
    failed  = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_image, url, OUTPUT_DIR): url
            for url in all_image_urls
        }
        for fut in as_completed(futures):
            url, ok = fut.result()
            if ok:
                success += 1
                print(f"  ✓  {os.path.basename(url_to_filename(url))}")
            else:
                failed += 1
                print(f"  ✗  {url}")

    print(f"\nDone. {success} downloaded, {failed} failed.")
    print(f"Photos saved in: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
