# MovieScope Backend (FastAPI + MySQL)

This backend connects to your existing MySQL schema from `movie_db_inserts.sql` (`movie`, `genre`, `movie_genre`, etc.).

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

## Notes

- Actor/director filtering requires cast/crew tables which are not present in your current SQL file.
  We can add them next using Kaggle `credits.csv`.

