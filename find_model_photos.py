"""
find_model_photos.py  --  Scan C:\\MyPhotos for photos containing people / models
=================================================================================
Uses OpenCV's DNN face detector (high-accuracy deep learning model) +
a full-body Haar cascade to find photos with people in them.

What counts as a "model photo":
  • ≥ 1 face detected  (portrait, headshot, group shot, fashion photo)
  • OR ≥ 1 full body detected when no face found

Results:
  - Copies (or moves) matching photos to  <source>\\model_photos\\
  • Writes a CSV report:  model_photos_report.csv

Usage:
    python find_model_photos.py                     # scan C:\\MyPhotos, copy matches
    python find_model_photos.py --dir D:\\Pictures   # custom folder
    python find_model_photos.py --move              # move instead of copy
    python find_model_photos.py --no-copy           # report only, no file operation
    python find_model_photos.py --confidence 0.7    # stricter face detection
"""

import argparse
import csv
import os
import shutil
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_DIR      = r"C:\MyPhotos"
OUTPUT_SUBDIR    = "model_photos"
REPORT_FILE      = "model_photos_report.csv"
PHOTO_EXTS       = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
                    ".webp", ".gif"}

# DNN face detector confidence threshold (0–1); lower = more detections
DEFAULT_CONFIDENCE = 0.60

# OpenCV DNN face detector model files (Caffe model – ships with opencv-python)
# We download them automatically if not present.
DNN_PROTOTXT_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/"
    "samples/dnn/face_detector/deploy.prototxt"
)
DNN_MODEL_URL = (
    "https://github.com/opencv/opencv_3rdparty/raw/refs/heads/"
    "dnn_samples_face_detector_20170830/"
    "res10_300x300_ssd_iter_140000.caffemodel"
)
MODELS_DIR = Path(__file__).parent / "cv_models"


# ── Model download ────────────────────────────────────────────────────────────

def ensure_model_files() -> tuple[Path, Path]:
    """Download DNN face detector files if not already present."""
    MODELS_DIR.mkdir(exist_ok=True)
    proto  = MODELS_DIR / "deploy.prototxt"
    caffe  = MODELS_DIR / "res10_300x300_ssd_iter_140000.caffemodel"

    if not proto.exists():
        print("Downloading face detector prototxt …", end=" ", flush=True)
        urllib.request.urlretrieve(DNN_PROTOTXT_URL, proto)
        print("done")

    if not caffe.exists():
        print("Downloading face detector model (~10 MB) …", end=" ", flush=True)
        urllib.request.urlretrieve(DNN_MODEL_URL, caffe)
        print("done")

    return proto, caffe


# ── Detection ─────────────────────────────────────────────────────────────────

def load_detectors(proto: Path, caffe: Path):
    face_net  = cv2.dnn.readNetFromCaffe(str(proto), str(caffe))
    body_cascade_path = cv2.data.haarcascades + "haarcascade_fullbody.xml"
    body_cascade = cv2.CascadeClassifier(body_cascade_path)
    return face_net, body_cascade


def detect_faces_dnn(img_bgr: np.ndarray, net, confidence_threshold: float
                     ) -> int:
    """Return number of faces detected with confidence ≥ threshold."""
    h, w = img_bgr.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(img_bgr, (300, 300)),
        scalefactor=1.0,
        size=(300, 300),
        mean=(104.0, 177.0, 123.0),
    )
    net.setInput(blob)
    detections = net.forward()
    count = 0
    for i in range(detections.shape[2]):
        conf = float(detections[0, 0, i, 2])
        if conf >= confidence_threshold:
            count += 1
    return count


def detect_bodies(img_bgr: np.ndarray, cascade) -> int:
    """Return number of full-body detections."""
    gray   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bodies = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3,
                                      minSize=(60, 120))
    return len(bodies) if bodies is not None and len(bodies) > 0 else 0


def analyse_photo(path: Path, face_net, body_cascade,
                  confidence: float) -> dict:
    """Return detection result dict for one photo."""
    result = {"path": path, "faces": 0, "bodies": 0,
              "is_model_photo": False, "error": ""}
    try:
        img = cv2.imdecode(
            np.frombuffer(path.read_bytes(), np.uint8),
            cv2.IMREAD_COLOR,
        )
        if img is None:
            result["error"] = "could not decode"
            return result

        faces  = detect_faces_dnn(img, face_net, confidence)
        bodies = detect_bodies(img, body_cascade) if faces == 0 else 0

        result["faces"]          = faces
        result["bodies"]         = bodies
        result["is_model_photo"] = (faces > 0) or (bodies > 0)
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

    # Ensure DNN models are available
    proto, caffe = ensure_model_files()
    face_net, body_cascade = load_detectors(proto, caffe)
    print("Detectors loaded.")

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
    results  = []
    matched  = []
    for i, p in enumerate(photos, 1):
        print(f"[{i:>4}/{len(photos)}] {p.name:<50}", end="\r")
        r = analyse_photo(p, face_net, body_cascade, args.confidence)
        results.append(r)
        if r["is_model_photo"]:
            matched.append(r)

    print(f"\nScanned {len(photos)} photos – {len(matched)} model photo(s) found.")

    # Copy / move
    if not args.no_copy and matched:
        op = "Moving" if args.move else "Copying"
        print(f"{op} {len(matched)} file(s) to {out_dir} …")
        for r in matched:
            dest = out_dir / r["path"].name
            # avoid name collision
            if dest.exists():
                stem = r["path"].stem
                suffix = r["path"].suffix
                dest = out_dir / f"{stem}_{id(r)}{suffix}"
            if args.move:
                shutil.move(str(r["path"]), dest)
            else:
                shutil.copy2(r["path"], dest)

    # CSV report
    report_path = root / REPORT_FILE
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["path", "faces", "bodies", "is_model_photo", "error"]
        )
        writer.writeheader()
        for r in results:
            writer.writerow({
                "path":           r["path"],
                "faces":          r["faces"],
                "bodies":         r["bodies"],
                "is_model_photo": r["is_model_photo"],
                "error":          r["error"],
            })

    print(f"Report saved: {report_path}")
    if not args.no_copy and matched:
        print(f"Model photos saved to: {out_dir}")

    # Summary
    print(f"\n{'='*50}")
    print(f"  Total scanned   : {len(photos)}")
    print(f"  Model photos    : {len(matched)}")
    print(f"  With faces      : {sum(1 for r in matched if r['faces'] > 0)}")
    print(f"  Bodies only     : {sum(1 for r in matched if r['faces']==0 and r['bodies']>0)}")
    print(f"  Errors          : {sum(1 for r in results if r['error'])}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
