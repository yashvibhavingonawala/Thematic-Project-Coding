"""
Build keyword-based movie recommendations using TF-IDF + cosine similarity.

Inputs (Kaggle):
- movies_metadata.csv (contains id, title)
- keywords.csv (contains id, keywords JSON-like text)

Output:
- keyword_recommendations.csv with columns:
  movie_id, recommended_movie_id, similarity_score

Notes for MovieCrew:
- By default we restrict to movie_ids present in your SQLite `movie` table so it matches the website DB.
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import sqlite3
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


def parse_keyword_text(raw: str) -> str:
    """
    keywords.csv stores a python-ish list of dicts as a string.
    Example:
      "[{'id': 931, 'name': 'jealousy'}, {'id': 4290, 'name': 'toy'}]"
    -> "jealousy toy"
    """
    s = (raw or "").strip()
    if not s or s == "[]":
        return ""
    try:
        data = ast.literal_eval(s)
        if not isinstance(data, list):
            return ""
        words: list[str] = []
        for item in data:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip().lower()
                if name:
                    words.append(name.replace(" ", "_"))
        return " ".join(words)
    except Exception:
        # keywords.csv sometimes has inconsistent escaping/quoting that breaks literal_eval.
        # Fallback to regex extraction which is good enough for similarity.
        words = []
        for name in re.findall(r"(?:'name'|\"name\")\s*:\s*(?:'([^']+)'|\"([^\"]+)\")", s):
            val = (name[0] or name[1] or "").strip().lower()
            if val:
                words.append(val.replace(" ", "_"))
        return " ".join(words)


def load_allowed_movie_ids(sqlite_path: Path) -> set[int]:
    con = sqlite3.connect(str(sqlite_path))
    try:
        cur = con.cursor()
        rows = cur.execute("SELECT movie_id FROM movie").fetchall()
        return {int(r[0]) for r in rows}
    finally:
        con.close()


def load_metadata(metadata_csv: Path, allowed_ids: set[int] | None) -> dict[int, str]:
    out: dict[int, str] = {}
    with metadata_csv.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mid = (row.get("id") or "").strip()
            if not mid.isdigit():
                continue
            movie_id = int(mid)
            if allowed_ids is not None and movie_id not in allowed_ids:
                continue
            title = (row.get("title") or "").strip()
            if not title:
                continue
            out[movie_id] = title
    return out


def load_keywords(keywords_csv: Path, allowed_ids: set[int] | None) -> dict[int, str]:
    out: dict[int, str] = {}
    with keywords_csv.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mid = (row.get("id") or "").strip()
            if not mid.isdigit():
                continue
            movie_id = int(mid)
            if allowed_ids is not None and movie_id not in allowed_ids:
                continue
            kw = parse_keyword_text(row.get("keywords") or "")
            if kw:
                out[movie_id] = kw
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", required=True, help="Path to movies_metadata.csv")
    ap.add_argument("--keywords", required=True, help="Path to keywords.csv")
    ap.add_argument("--out", default="keyword_recommendations.csv", help="Output CSV path")
    ap.add_argument("--topk", type=int, default=10, help="Recommendations per movie (default 10)")
    ap.add_argument("--sqlite", default="", help="Optional SQLite DB path to restrict IDs to the site DB")
    args = ap.parse_args()

    metadata_csv = Path(args.metadata).expanduser().resolve()
    keywords_csv = Path(args.keywords).expanduser().resolve()
    out_csv = Path(args.out).expanduser().resolve()

    if not metadata_csv.exists():
        raise SystemExit(f"Missing metadata CSV: {metadata_csv}")
    if not keywords_csv.exists():
        raise SystemExit(f"Missing keywords CSV: {keywords_csv}")

    allowed_ids = None
    if args.sqlite:
        sqlite_path = Path(args.sqlite).expanduser().resolve()
        if not sqlite_path.exists():
            raise SystemExit(f"Missing sqlite DB: {sqlite_path}")
        allowed_ids = load_allowed_movie_ids(sqlite_path)

    titles = load_metadata(metadata_csv, allowed_ids)
    kw = load_keywords(keywords_csv, allowed_ids)

    # Merge
    rows = [(mid, titles[mid], kw[mid]) for mid in titles.keys() if mid in kw and kw[mid].strip()]

    # Dedupe by movie_id
    seen: set[int] = set()
    merged: list[tuple[int, str, str]] = []
    for mid, title, text in rows:
        if mid in seen:
            continue
        seen.add(mid)
        merged.append((mid, title, text))

    if not merged:
        raise SystemExit("No merged rows found (check that keywords.csv matches your movie ids).")

    movie_ids = [m[0] for m in merged]
    keyword_texts = [m[2] for m in merged]

    vectorizer = TfidfVectorizer(
        min_df=2,
        max_df=0.9,
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b\w+\b",
    )
    tfidf = vectorizer.fit_transform(keyword_texts)

    # cosine similarity via linear kernel on normalized tf-idf vectors
    sim = linear_kernel(tfidf, tfidf)

    topk = max(1, int(args.topk))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["movie_id", "recommended_movie_id", "similarity_score"])
        for i, mid in enumerate(movie_ids):
            scores = sim[i]
            # argsort descending; skip itself
            best_idx = scores.argsort()[::-1]
            added = 0
            for j in best_idx:
                if int(j) == i:
                    continue
                score = float(scores[j])
                if score <= 0:
                    break
                w.writerow([mid, movie_ids[int(j)], f"{score:.6f}"])
                added += 1
                if added >= topk:
                    break

    print(f"Wrote {out_csv} for {len(movie_ids)} movies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

