"""
Import local poster image files into the frontend's `assets/posters/` folder.

Why this exists:
- The Kaggle `movies_metadata.csv` contains a `poster_path` like `/rhIRbceoE9lR4veEXuwCC2wARtG.jpg`
- Many datasets ship the actual poster images as local JPG/PNG files named by that basename
  (e.g. `rhIRbceoE9lR4veEXuwCC2wARtG.jpg`).

This script copies those local images into:
- `Thematic project/assets/posters/<movie_id>.jpg`  (frontend first-choice)
- `Thematic project/assets/posters/<poster_basename>.jpg` (fallback)

Usage:
  python backend/scripts/import_local_posters.py \
    --csv "movies_metadata.csv" \
    --src "/path/to/your/poster_images_folder" \
    --out "assets/posters" \
    --limit 20000

Notes:
- We don't resize/re-encode images; we copy as-is.
- Supported extensions: .jpg, .jpeg, .png, .webp
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path


SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _find_file_by_basename(src_dir: Path, basename: str) -> Path | None:
    base = basename.strip().lstrip("/").strip()
    if not base:
        return None

    # Exact match first
    p = src_dir / base
    if p.exists() and p.is_file():
        return p

    # Try other extensions (some datasets omit extension)
    stem, ext = os.path.splitext(base)
    candidates = []
    if ext.lower() in SUPPORTED_EXTS:
        candidates.append(stem)
    else:
        stem = base
    for e in SUPPORTED_EXTS:
        candidates.append(stem + e)
        candidates.append(stem + e.upper())
    for name in candidates:
        p2 = src_dir / name
        if p2.exists() and p2.is_file():
            return p2
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to movies_metadata.csv")
    ap.add_argument("--src", required=True, help="Folder containing local poster images")
    ap.add_argument("--out", default="assets/posters", help="Output folder (default: assets/posters)")
    ap.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = all)")
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    src_dir = Path(args.src).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not src_dir.exists():
        raise SystemExit(f"Source folder not found: {src_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    copied = 0
    missing = 0

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if args.limit and processed >= args.limit:
                break
            processed += 1

            movie_id = (row.get("id") or "").strip()
            poster_path = (row.get("poster_path") or "").strip()
            if not movie_id or not poster_path:
                continue

            src_file = _find_file_by_basename(src_dir, poster_path)
            if not src_file:
                missing += 1
                continue

            # Copy as movie_id.<ext> (preferred by frontend)
            ext = src_file.suffix.lower() if src_file.suffix else ".jpg"
            out_by_id = out_dir / f"{movie_id}{ext}"
            if not out_by_id.exists():
                shutil.copy2(src_file, out_by_id)
                copied += 1

            # Also copy as poster basename (frontend fallback)
            base = poster_path.lstrip("/").strip()
            if base:
                out_by_base = out_dir / base
                if not out_by_base.exists():
                    shutil.copy2(src_file, out_by_base)

    print(
        f"Processed {processed} rows. Copied {copied} posters by movie_id. Missing source for {missing} rows."
    )
    print(f"Output folder: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

