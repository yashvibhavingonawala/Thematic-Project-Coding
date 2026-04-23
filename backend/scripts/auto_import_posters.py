"""
Auto-detect and import local poster images for MovieCrew.

Goal:
- You already have movies in SQLite/CSV and a local dataset of poster JPG files.
- The website loads posters from `Thematic project/assets/posters/`.
- This script tries to FIND where your poster image dataset lives, then copies posters into `assets/posters/`.

How it works:
1) Reads `movies_metadata.csv` and collects poster basenames from `poster_path`
   (e.g. "/rhIRbceoE9lR4veEXuwCC2wARtG.jpg" -> "rhIRbceoE9lR4veEXuwCC2wARtG.jpg")
2) Searches likely directories (Downloads/Documents/Desktop) for a folder containing many of those files
3) Once found, copies posters into `assets/posters/` as:
   - `<movie_id>.<ext>` (preferred)
   - `<poster_basename>` (fallback)

Usage:
  python backend/scripts/auto_import_posters.py

Optional:
  python backend/scripts/auto_import_posters.py --root "/Users/yashvigonawala/Downloads"
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path


SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _poster_basenames_from_csv(csv_path: Path, limit: int = 0) -> dict[str, str]:
    """
    Returns mapping: movie_id -> poster_basename (with extension).
    """
    out: dict[str, str] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            mid = (row.get("id") or "").strip()
            p = (row.get("poster_path") or "").strip()
            if not mid or not p:
                continue
            base = p.lstrip("/").strip()
            if not base:
                continue
            out[mid] = base
    return out


def _score_folder(folder: Path, wanted_bases: set[str], sample_limit: int = 4000) -> int:
    """
    Score a folder by how many wanted poster basenames it contains.
    We only sample up to sample_limit filenames to keep it fast.
    """
    try:
        names = []
        for j, p in enumerate(folder.iterdir()):
            if j >= sample_limit:
                break
            if p.is_file():
                names.append(p.name)
        if not names:
            return 0
        return sum(1 for n in names if n in wanted_bases)
    except Exception:
        return 0


def _find_best_candidate_folder(root: Path, wanted_bases: set[str], max_dirs: int = 2500) -> Path | None:
    best: tuple[int, Path] | None = None
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        seen += 1
        if seen > max_dirs:
            break

        # Prune noisy dirs
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {".git", "node_modules", "__pycache__", ".venv", "venv", ".cache", "Library"}
            and not d.startswith(".")
        ]

        folder = Path(dirpath)
        # quick heuristic: must have a bunch of image files
        img_count = 0
        for name in filenames[:3000]:
            if name.lower().endswith(SUPPORTED_EXTS):
                img_count += 1
        if img_count < 200:
            continue

        score = sum(1 for n in filenames[:6000] if n in wanted_bases)
        if score <= 0:
            continue

        if best is None or score > best[0]:
            best = (score, folder)

        # Early exit if extremely likely
        if score >= 800:
            break

    return best[1] if best else None


def _copy_posters(csv_map: dict[str, str], src_dir: Path, out_dir: Path, limit: int = 0) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    missing = 0
    processed = 0

    for mid, base in csv_map.items():
        processed += 1
        if limit and processed > limit:
            break
        src = src_dir / base
        if not src.exists():
            # Try alternative extensions
            stem, ext = os.path.splitext(base)
            found = None
            for e in SUPPORTED_EXTS:
                cand = src_dir / (stem + e)
                if cand.exists():
                    found = cand
                    break
            if found is None:
                missing += 1
                continue
            src = found

        ext = src.suffix.lower() if src.suffix else ".jpg"
        dst_by_id = out_dir / f"{mid}{ext}"
        if not dst_by_id.exists():
            shutil.copy2(src, dst_by_id)
            copied += 1

        dst_by_base = out_dir / base
        if base and not dst_by_base.exists():
            shutil.copy2(src, dst_by_base)

    return {"processed": processed, "copied": copied, "missing": missing, "src": str(src_dir), "out": str(out_dir)}


def main() -> int:
    here = Path(__file__).resolve()
    project_root = here.parents[2]  # .../Thematic project/

    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(project_root / "backend" / "data" / "movies_metadata.csv"))
    ap.add_argument("--out", default=str(project_root / "assets" / "posters"))
    ap.add_argument("--root", default="", help="Optional root to search under (default: common folders)")
    ap.add_argument("--scan_limit_movies", type=int, default=12000, help="How many movies to sample from CSV for matching")
    ap.add_argument("--max_dirs", type=int, default=2500, help="Max folders to scan while searching")
    ap.add_argument("--import_limit", type=int, default=0, help="Max posters to import (0 = all)")
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        raise SystemExit(f"movies_metadata.csv not found at: {csv_path}")

    out_dir = Path(args.out).expanduser().resolve()

    csv_map = _poster_basenames_from_csv(csv_path, limit=args.scan_limit_movies)
    wanted_bases = set(csv_map.values())
    if not wanted_bases:
        raise SystemExit("No poster_path values found in CSV.")

    roots: list[Path]
    if args.root:
        roots = [Path(args.root).expanduser().resolve()]
    else:
        home = Path.home()
        roots = [home / "Downloads", home / "Documents", home / "Desktop", home]

    best = None
    for r in roots:
        if r.exists():
            cand = _find_best_candidate_folder(r, wanted_bases, max_dirs=args.max_dirs)
            if cand:
                best = cand
                break

    if not best:
        print("Could not auto-find a poster image folder.")
        print("Please run again with --root pointing at the folder that contains the JPG posters.")
        return 2

    report = _copy_posters(csv_map, best, out_dir, limit=args.import_limit)
    print("Auto poster import finished.")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

