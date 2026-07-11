"""
remove_dupes.py  --  Remove duplicate photos from C:\\MyPhotos
============================================================
Two-pass detection:
  1. Exact duplicates  – identical SHA-256 hash (byte-for-byte same file)
  2. Near duplicates   – perceptual hash (pHash) difference ≤ PHASH_THRESHOLD
     (catches recompressed / slightly edited / resized copies of the same photo)

Safe by default:
  • DRY-RUN mode is ON unless you pass --delete
  • Duplicates are listed in a report file before anything is removed
  • For each duplicate group the LARGEST file is kept (best quality)

Usage:
    python remove_dupes.py                   # dry-run: report only
    python remove_dupes.py --delete          # actually delete duplicates
    python remove_dupes.py --dir D:\\Photos   # custom folder
    python remove_dupes.py --no-perceptual   # exact duplicates only
"""

import argparse
import hashlib
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import imagehash
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_DIR      = r"C:\MyPhotos"
PHOTO_EXTS       = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
                    ".webp", ".heic", ".heif", ".avif"}
PHASH_THRESHOLD  = 8      # hamming distance; 0 = identical, ≤10 = near-dupe
REPORT_FILE      = "dupes_report.txt"


# ── Helpers ───────────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def phash(path: Path):
    try:
        return imagehash.phash(Image.open(path).convert("RGB"))
    except Exception:
        return None


def iter_photos(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in PHOTO_EXTS:
            yield p


def best_to_keep(paths: list[Path]) -> Path:
    """Keep the largest file (highest resolution / quality)."""
    return max(paths, key=lambda p: p.stat().st_size)


# ── Core ──────────────────────────────────────────────────────────────────────

def find_exact_dupes(photos: list[Path]) -> list[list[Path]]:
    print("\n[1/2] Hashing files for exact duplicates …")
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for i, p in enumerate(photos, 1):
        if i % 100 == 0:
            print(f"  {i}/{len(photos)}", end="\r")
        by_hash[sha256(p)].append(p)
    groups = [v for v in by_hash.values() if len(v) > 1]
    print(f"  Found {len(groups)} exact-duplicate group(s)          ")
    return groups


def find_perceptual_dupes(photos: list[Path],
                          already_duped: set[Path]) -> list[list[Path]]:
    """Find near-duplicates among files not already caught by exact matching."""
    candidates = [p for p in photos if p not in already_duped]
    print(f"\n[2/2] Perceptual hashing {len(candidates)} remaining files …")

    hashes: list[tuple[Path, object]] = []
    for i, p in enumerate(candidates, 1):
        if i % 100 == 0:
            print(f"  {i}/{len(candidates)}", end="\r")
        h = phash(p)
        if h is not None:
            hashes.append((p, h))

    # O(n²) comparison – fine for typical photo libraries (< 50 k photos)
    used = set()
    groups = []
    for i, (p1, h1) in enumerate(hashes):
        if p1 in used:
            continue
        group = [p1]
        for p2, h2 in hashes[i + 1:]:
            if p2 not in used and (h1 - h2) <= PHASH_THRESHOLD:
                group.append(p2)
                used.add(p2)
        if len(group) > 1:
            used.add(p1)
            groups.append(group)

    print(f"  Found {len(groups)} near-duplicate group(s)           ")
    return groups


def write_report(exact_groups: list[list[Path]],
                 near_groups: list[list[Path]],
                 report_path: Path) -> list[Path]:
    """Write human-readable report and return flat list of files to delete."""
    to_delete: list[Path] = []
    lines = [
        f"Duplicate Photo Report – {datetime.now():%Y-%m-%d %H:%M:%S}",
        "=" * 70,
        "",
    ]

    def add_group(label: str, groups: list[list[Path]]):
        nonlocal to_delete
        lines.append(f"{'─'*70}")
        lines.append(f"{label}  ({len(groups)} group(s))")
        lines.append(f"{'─'*70}")
        for g in groups:
            keep = best_to_keep(g)
            dupes = [p for p in g if p != keep]
            to_delete.extend(dupes)
            lines.append(f"  KEEP   ({keep.stat().st_size:>10,} B)  {keep}")
            for d in dupes:
                lines.append(f"  DELETE ({d.stat().st_size:>10,} B)  {d}")
            lines.append("")

    add_group("EXACT DUPLICATES", exact_groups)
    add_group("NEAR DUPLICATES (perceptual hash)", near_groups)

    lines += [
        "=" * 70,
        f"Total files to delete: {len(to_delete)}",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return to_delete


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Remove duplicate photos")
    ap.add_argument("--dir",          default=DEFAULT_DIR,
                    help="Folder to scan (default: C:\\MyPhotos)")
    ap.add_argument("--delete",       action="store_true",
                    help="Actually delete duplicates (default: dry-run)")
    ap.add_argument("--no-perceptual", action="store_true",
                    help="Skip perceptual (near-duplicate) detection")
    ap.add_argument("--threshold",    type=int, default=PHASH_THRESHOLD,
                    help="pHash hamming threshold (default 8)")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        sys.exit(f"ERROR: Folder not found: {root}")

    print(f"Scanning {root} …")
    photos = list(iter_photos(root))
    print(f"Found {len(photos)} photo file(s)")

    if not photos:
        print("Nothing to do.")
        return

    exact_groups = find_exact_dupes(photos)

    near_groups: list[list[Path]] = []
    if not args.no_perceptual:
        already = {p for g in exact_groups for p in g}
        near_groups = find_perceptual_dupes(photos, already)

    report_path = root / REPORT_FILE
    to_delete   = write_report(exact_groups, near_groups, report_path)

    print(f"\nReport written to: {report_path}")
    print(f"Files to delete:   {len(to_delete)}")

    if not to_delete:
        print("No duplicates found – nothing to delete.")
        return

    if not args.delete:
        print("\nDRY-RUN mode: no files deleted.")
        print("Review the report, then re-run with --delete to remove duplicates.")
        return

    print("\nDeleting duplicates …")
    removed = 0
    for p in to_delete:
        try:
            p.unlink()
            print(f"  Deleted: {p}")
            removed += 1
        except Exception as e:
            print(f"  ERROR deleting {p}: {e}")

    print(f"\nDone. {removed}/{len(to_delete)} files deleted.")


if __name__ == "__main__":
    main()
