"""
Bollywood Trending Music Downloader
------------------------------------
Fetches the current trending Bollywood/Hindi songs from YouTube Music
and downloads them as MP3 files with embedded metadata and cover art.

Strategy (tried in order, first success wins):
  1. ytmusicapi charts for India  (get_charts country="IN")
  2. ytmusicapi search            ("bollywood trending 2025", filter="songs")
  3. yt-dlp YouTube search        (ytsearchN:...)

Usage:
    python bollywood_trending.py [--limit N] [--output DIR] [--no-download] [--query Q]

Options:
    --limit N       Number of songs to fetch (default: 20)
    --output DIR    Output directory for MP3s (default: ./bollywood-trending)
    --no-download   Only list trending songs, don't download
    --query Q       Custom search query  (default: "bollywood trending new songs 2025")
"""

import argparse
import io
import json
import os
import shutil
import sys
from pathlib import Path

# Force UTF-8 output on Windows so Unicode characters don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from ytmusicapi import YTMusic
except ImportError:
    sys.exit("ytmusicapi not installed.  Run: pip install ytmusicapi")

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp not installed.  Run: pip install yt-dlp")


# ── ffmpeg auto-detection ──────────────────────────────────────────────────

def find_ffmpeg() -> str | None:
    """Return the directory containing ffmpeg.exe, or None if not found."""
    # 1. Already on PATH
    if shutil.which("ffmpeg"):
        return str(Path(shutil.which("ffmpeg")).parent)

    # 2. WinGet install location (Windows)
    winget_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_root.exists():
        for exe in winget_root.rglob("ffmpeg.exe"):
            return str(exe.parent)

    # 3. Common install paths
    candidates = [
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Tools\ffmpeg\bin",
    ]
    for c in candidates:
        if Path(c, "ffmpeg.exe").exists():
            return c

    return None


# ── helpers ────────────────────────────────────────────────────────────────

def separator(char="-", width=60):
    print(char * width)


def _artists_str(artists_list: list) -> str:
    if not artists_list:
        return ""
    names = []
    for a in artists_list:
        if isinstance(a, dict):
            names.append(a.get("name", ""))
        elif isinstance(a, str):
            names.append(a)
    return ", ".join(filter(None, names))


# ── source 1: ytmusicapi charts ────────────────────────────────────────────

def fetch_via_charts(limit: int) -> list[dict]:
    """India Top Songs via YouTube Music Charts API."""
    ytm = YTMusic()
    print("[1/3] Trying YouTube Music India Charts ...")
    try:
        charts = ytm.get_charts(country="IN")
        raw = charts.get("songs", {}).get("items", [])
        tracks = []
        for item in raw[:limit]:
            vid = item.get("videoId") or item.get("playlistItemData", {}).get("videoId", "")
            title = item.get("title", "Unknown")
            artists = _artists_str(item.get("artists", []))
            if vid:
                tracks.append({"title": title, "artist": artists, "videoId": vid})
        if tracks:
            print(f"    -> Got {len(tracks)} songs from India Charts\n")
            return tracks
        print("    -> Charts returned no songs.")
    except Exception as e:
        print(f"    -> Charts unavailable: {e}")
    return []


# ── source 2: ytmusicapi search ────────────────────────────────────────────

def fetch_via_ytm_search(limit: int, query: str) -> list[dict]:
    """Search YouTube Music for trending Bollywood songs (no auth needed)."""
    ytm = YTMusic()
    print(f"[2/3] Searching YouTube Music: '{query}' ...")
    try:
        results = ytm.search(query, filter="songs", limit=limit)
        tracks = []
        for item in results[:limit]:
            vid = item.get("videoId", "")
            title = item.get("title", "Unknown")
            artists = _artists_str(item.get("artists", []))
            if vid:
                tracks.append({"title": title, "artist": artists, "videoId": vid})
        if tracks:
            print(f"    -> Got {len(tracks)} songs via YTM search\n")
            return tracks
        print("    -> Search returned no results.")
    except Exception as e:
        print(f"    -> YTM search failed: {e}")
    return []


# ── source 3: yt-dlp YouTube search ────────────────────────────────────────

def fetch_via_ytdlp_search(limit: int, query: str) -> list[dict]:
    """Use yt-dlp's built-in YouTube search as last resort."""
    print(f"[3/3] Falling back to yt-dlp YouTube search: '{query}' ...")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    tracks = []
    search_url = f"ytsearch{limit}:{query}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            for entry in (info.get("entries") or [])[:limit]:
                vid = entry.get("id", "")
                title = entry.get("title", "Unknown")
                artist = entry.get("channel", entry.get("uploader", ""))
                if vid:
                    tracks.append({"title": title, "artist": artist, "videoId": vid})
        if tracks:
            print(f"    -> Got {len(tracks)} songs via yt-dlp search\n")
    except Exception as e:
        print(f"    -> yt-dlp search failed: {e}")
    return tracks


# ── fetch dispatcher ────────────────────────────────────────────────────────

def fetch_trending(limit: int, query: str) -> list[dict]:
    tracks = fetch_via_charts(limit)
    if not tracks:
        tracks = fetch_via_ytm_search(limit, query)
    if not tracks:
        tracks = fetch_via_ytdlp_search(limit, query)
    return tracks


# ── display ────────────────────────────────────────────────────────────────

def print_tracklist(tracks: list[dict]):
    separator()
    print(f"{'#':<4}  {'Title':<45}  Artist")
    separator()
    for i, t in enumerate(tracks, 1):
        title = (t["title"] or "")[:44]
        artist = (t["artist"] or "-")[:35]
        print(f"{i:<4}  {title:<45}  {artist}")
    separator()
    print()


# ── download ────────────────────────────────────────────────────────────────

def download_tracks(tracks: list[dict], output_dir: Path) -> tuple[list, list]:
    output_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_dir = find_ffmpeg()
    if ffmpeg_dir:
        print(f"Using ffmpeg from: {ffmpeg_dir}\n")
    else:
        print("WARNING: ffmpeg not found. MP3 conversion will be skipped.\n"
              "         Install ffmpeg and add it to PATH for full functionality.\n")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
        "writethumbnail": True,
        "embedthumbnail": True,
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": True,
        "retries": 3,
    }

    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    success, failed = [], []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, track in enumerate(tracks, 1):
            vid = track.get("videoId", "")
            title = track.get("title", "Unknown")
            artist = track.get("artist", "-")

            if not vid:
                print(f"[{i}/{len(tracks)}] WARNING: no videoId for '{title}', skipping.")
                failed.append(title)
                continue

            url = f"https://www.youtube.com/watch?v={vid}"
            print(f"\n[{i}/{len(tracks)}] {title}")
            print(f"    Artist : {artist}")
            print(f"    URL    : {url}")

            try:
                ret = ydl.download([url])
                if ret == 0:
                    success.append(title)
                    print("    -> Done")
                else:
                    failed.append(title)
                    print("    -> FAILED (yt-dlp non-zero exit)")
            except Exception as e:
                failed.append(title)
                print(f"    -> ERROR: {e}")

    return success, failed


# ── main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download trending Bollywood music from YouTube Music")
    parser.add_argument("--limit",       type=int, default=20,
                        help="Number of songs to fetch (default: 20)")
    parser.add_argument("--output",      type=str, default="bollywood-trending",
                        help="Output folder (default: ./bollywood-trending)")
    parser.add_argument("--no-download", action="store_true",
                        help="List only, skip downloading")
    parser.add_argument("--query",       type=str,
                        default="bollywood trending new songs 2025",
                        help="Search query override")
    args = parser.parse_args()

    print()
    separator("=")
    print("  Bollywood Trending Music Downloader")
    separator("=")
    print()

    tracks = fetch_trending(args.limit, args.query)

    if not tracks:
        print("ERROR: Could not fetch any trending tracks.")
        print("       Check your internet connection and try again.")
        sys.exit(1)

    print(f"Found {len(tracks)} trending Bollywood tracks:\n")
    print_tracklist(tracks)

    # Always save metadata
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_file = out_dir / "trending_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as fh:
        json.dump(tracks, fh, indent=2, ensure_ascii=False)
    print(f"Metadata saved -> {meta_file}\n")

    if args.no_download:
        print("--no-download flag set. Skipping audio download.")
        return

    print(f"Downloading {len(tracks)} tracks to: {out_dir.resolve()}\n")
    success, failed = download_tracks(tracks, out_dir)

    print()
    separator("=")
    print(f"  Downloaded : {len(success)}/{len(tracks)}")
    if failed:
        print(f"  Failed     : {len(failed)}")
        for name in failed:
            print(f"    - {name}")
    separator("=")
    print(f"\nFiles saved to: {out_dir.resolve()}\n")


if __name__ == "__main__":
    main()
