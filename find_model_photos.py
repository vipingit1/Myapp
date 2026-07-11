"""
find_model_photos.py  --  Scan C:\\MyPhotos for photos containing people / models
=================================================================================
Uses OpenCV's built-in YuNet face detector (ONNX, works with OpenCV 4.8+/5.x)
to find photos with people in them.

What counts as a "model photo":
  - >= 1 face detected at normal confidence  (portrait, headshot, group shot)
  - OR >= 1 face detected at reduced confidence (partially obscured faces,
    side profiles, model shots where face is smaller / angled)

Results:
  - Copies (or moves) matching photos to  <source>\\model_photos\\
  - Writes a CSV report:  model_photos_report.csv

Usage:
    python find_model_photos.py                     # scan C:\\MyPhotos, copy matches
    python find_model_photos.py --dir D:\\Pictures   # custom folder
    python find_model_photos.py --move              # move instead of copy
    python find_model_photos.py --no-copy           # report only, no file operation
    python find_model_photos.py --confidence 0.7    # stricter face detection (default 0.6)
"""

import argparse
import csv
import shutil
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_DIR       = r"C:\MyPhotos"
OUTPUT_SUBDIR     = "model_photos"
REPORT_FILE       = "model_photos_report.csv"
PHOTO_EXTS        = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
                     ".webp", ".gif"}

DEFAULT_CONFIDENCE = 0.60    # primary threshold
LOW_CONFIDENCE     = 0.35    # fallback for partial/angled faces

# YuNet ONNX model – works with cv2.FaceDetectorYN (OpenCV 4.8+ / 5.x)
YUNET_URL  = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
MODELS_DIR = Path(__file__).parent / "cv_models"


# ── Model download ────────────────────────────────────────────────────────────

def ensure_yunet() -> Path:
    """Download YuNet ONNX model if not already present. Returns path."""
    MODELS_DIR.mkdir(exist_ok=True)
    model_path = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
    if not model_path.exists():
        print("Downloading YuNet face detector model (~400 KB) ...", end=" ", flush=True)
        urllib.request.urlretrieve(YUNET_URL, model_path)
        print("done")
    return model_path


# ── Detection ─────────────────────────────────────────────────────────────────

def load_detector(yunet_path: Path):
    """Load YuNet face detector."""
    return cv2.FaceDetectorYN.create(
        str(yunet_path),
        config="",
        input_size=(320, 320),
        score_threshold=0.6,
        nms_threshold=0.3,
        top_k=5000,
    )


def count_faces(img_bgr: np.ndarray, detector, threshold: float) -> int:
    """Return number of faces detected with score >= threshold."""
    h, w = img_bgr.shape[:2]
    detector.setInputSize((w, h))
    detector.setScoreThreshold(threshold)
    _, faces = detector.detect(img_bgr)
    return 0 if faces is None else len(faces)


def analyse_photo(path: Path, detector, confidence: float) -> dict:
    """Return detection result dict for one photo."""
    result = {"path": path, "faces": 0, "low_conf_faces": 0,
              "is_model_photo": False, "error": ""}
    try:
        img = cv2.imdecode(
            np.frombuffer(path.read_bytes(), np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img is None:
            result["error"] = "could not decode"
            return result

        faces = count_faces(img, detector, confidence)
        low   = count_faces(img, detector, LOW_CONFIDENCE) if faces == 0 else 0

        result["faces"]          = faces
        result["low_conf_faces"] = low
        result["is_model_photo"] = (faces > 0) or (low > 0)
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Find photos with people/models")
    ap.add_argument("--dir",        default=DEFAULT_DIR,
                    help="Folder to scan (default: C:\\MyPhotos)")
    ap.add_argument("--move",       action="store_true",
                    help="Move matches instead of copying")
    ap.add_argument("--no-copy",    action="store_true",
                    help="Report only; do not copy/move any files")
    ap.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE,
                    help="Face detection confidence threshold 0-1 (default 0.6)")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        sys.exit(f"ERROR: Folder not found: {root}")

    yunet_path = ensure_yunet()
    detector   = load_detector(yunet_path)
    print(f"YuNet face detector loaded (OpenCV {cv2.__version__}).")

    # Collect photos
    photos = [p for p in root.rglob("*")
              if p.is_file() and p.suffix.lower() in PHOTO_EXTS]
    print(f"Found {len(photos)} photo(s) in {root}")

    if not photos:
        print("Nothing to scan.")
        return

    # Output folder
    out_dir = root / OUTPUT_SUBDIR
    if not args.no_copy:
        out_dir.mkdir(exist_ok=True)

    # Analyse
    results = []
    matched = []
    for i, p in enumerate(photos, 1):
        print(f"[{i:>4}/{len(photos)}] {p.name:<50}", end="\r")
        r = analyse_photo(p, detector, args.confidence)
        results.append(r)
        if r["is_model_photo"]:
            matched.append(r)

    print(f"\nScanned {len(photos)} photos -- {len(matched)} model photo(s) found.")

    # Copy / move
    if not args.no_copy and matched:
        op = "Moving" if args.move else "Copying"
        print(f"{op} {len(matched)} file(s) to {out_dir} ...")
        for r in matched:
            dest = out_dir / r["path"].name
            if dest.exists():
                dest = out_dir / f"{r['path'].stem}_{id(r)}{r['path'].suffix}"
            if args.move:
                shutil.move(str(r["path"]), dest)
            else:
                shutil.copy2(r["path"], dest)

    # CSV report
    report_path = root / REPORT_FILE
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["path", "faces", "low_conf_faces", "is_model_photo", "error"]
        )
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"Report saved: {report_path}")
    if not args.no_copy and matched:
        print(f"Model photos saved to: {out_dir}")

    print(f"\n{'='*50}")
    print(f"  Total scanned      : {len(photos)}")
    print(f"  Model photos       : {len(matched)}")
    print(f"  High-conf faces    : {sum(1 for r in matched if r['faces'] > 0)}")
    print(f"  Low-conf faces     : {sum(1 for r in matched if r['faces']==0 and r['low_conf_faces']>0)}")
    print(f"  Errors             : {sum(1 for r in results if r['error'])}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
