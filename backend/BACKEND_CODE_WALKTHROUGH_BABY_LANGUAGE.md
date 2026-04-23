# Backend Code Walkthrough (Baby Language)

This file explains the backend code in simple words, so everyone understands what “backend” is and how our backend will work.

---

## What we built

We built a backend using:
- **FastAPI** (Python web framework)
- **MySQL database** (where movie data lives)
- **SQLAlchemy** (tool to talk to database from Python)

---

## Folder structure (what each file is for)

- `backend/.env.example`
  - A template file where we put settings (database username/password, port, etc.)
  - We do **not** hardcode these values in code.

- `backend/requirements.txt`
  - List of Python libraries we need.

- `backend/app/config.py`
  - Reads settings from `.env`
  - Builds the MySQL connection URL

- `backend/app/db.py`
  - Creates the database engine
  - Creates a database session (connection) when an API request comes in

- `backend/app/models.py`
  - Describes database tables in Python form:
    - `movie`
    - `genre`
    - `movie_genre`

- `backend/app/schemas.py`
  - Describes what JSON we return to the frontend (response shape)

- `backend/app/main.py`
  - The main FastAPI app
  - Has API endpoints like `/movies` and `/genres`

---

## What happens when frontend calls the backend?

Example: user clicks filters and frontend calls:

`GET /movies?year_from=2010&year_to=2020`

Then:
1. FastAPI receives the request.
2. It opens a database session (connection).
3. It builds a SQL query with filters.
4. MySQL returns matching movies.
5. Backend turns the movies into JSON.
6. Frontend receives JSON and shows it on the page.

---

## Why we use `.env` (soft coding)

We do not want things like password inside code.

So we keep these values in `.env`:
- database host
- database username
- database password
- database name

That is “soft-coded”:
- code stays same
- only `.env` changes on different computers

---

## Endpoint 1: `GET /health`

Purpose:
- quick test to see if backend server is running

Returns:

```json
{ "status": "ok" }
```

---

## Endpoint 2: `GET /genres`

Purpose:
- frontend can show all genres (Action, Comedy, etc.)

Backend does:
- SELECT all genres from `genre` table
- returns them as JSON list

---

## Endpoint 3: `GET /movies`

Purpose:
- returns movies list for the main page
- supports filters and search

Supported filters:
- `q` = search by movie title
- `genres` = genre IDs (repeat parameter)
- `year_from`, `year_to`
- `budget_min`, `budget_max`
- `revenue_min`, `revenue_max`
- `page`, `page_size` for pagination

Important:
- We do not send “everything”
- We send only the fields needed for list view

How genre filter works:
- `movie` table does not store genre name directly
- We join via `movie_genre` to connect movies to genres

---

## Endpoint 4: `GET /movies/{movie_id}`

Purpose:
- returns full details for 1 movie
- includes genres list

---

## What about actor/director filters?

Your current MySQL SQL file does NOT include cast/crew tables.

So to support:
- “films starring selected actors”
- “films directed by selected director”
- “search actor/director”

We will add new tables later:
- `person`
- `movie_cast`
- `movie_crew` (with job = Director)

Then we can implement:
- `/movies?actor=...`
- `/movies?director=...`

---

## How to run the backend

1) Install dependencies:

```bash
cd "/Users/yashvigonawala/Thematic project/backend"
python3 -m pip install -r requirements.txt
```

2) Create `.env`:

```bash
cp .env.example .env
```

3) Start server:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

4) Open docs:
- `http://127.0.0.1:8000/docs`

---

## Very small summary

- FastAPI gives us URLs like `/movies`
- Our code uses MySQL to find the correct movies
- We return JSON to the frontend
- Frontend shows that JSON to the user

