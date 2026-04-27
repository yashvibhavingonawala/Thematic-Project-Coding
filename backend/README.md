# MovieScope Backend (FastAPI + SQLite)

This backend uses a local SQLite database (see `backend/data/movie_db.sqlite3`).

## Setup

1) Create a virtual environment (or use your existing one) and install deps:

```bash
cd "/Users/yashvigonawala/Thematic project/backend"
python3 -m pip install -r requirements.txt
```

2) Create your `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and set:
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`

3) Run the API server:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:
- API health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

## Endpoints

- `GET /genres`
- `GET /movies`
  - Filters:
    - `q`
    - `genres` (repeat param): `?genres=28&genres=12`
    - `year_from`, `year_to`
    - `budget_min`, `budget_max`
    - `revenue_min`, `revenue_max`
    - `page`, `page_size`
- `GET /movies/{movie_id}`
- `GET /movies/{movie_id}/recommendations` (keyword similarity, top 10)

## Keyword-based recommendations (TF-IDF)

1) Build `keyword_recommendations.csv` from the Kaggle dataset:

```bash
python3 "scripts/build_keyword_recommendations.py" \
  --metadata "data/movies_metadata.csv" \
  --keywords "data/archive/keywords.csv" \
  --sqlite "data/movie_db.sqlite3" \
  --out "data/keyword_recommendations.csv"
```

2) Import into SQLite:

```bash
python3 "scripts/import_keyword_recommendations.py" \
  --csv "data/keyword_recommendations.csv" \
  --sqlite "data/movie_db.sqlite3"
```

## Notes

- Actor/director filtering requires cast/crew tables which are not present in your current SQL file.
  We can add them next using Kaggle `credits.csv`.

