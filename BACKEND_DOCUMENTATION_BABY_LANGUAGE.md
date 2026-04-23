# Movie Database Project — Backend Documentation (Very Simple Language)

This document explains what **backend** means and exactly **how we will build the backend** for our Movie Database Presentation Tool project.

---

## What are we building?

We are building a website where users can:
- browse movies
- open a movie and see details
- see cast (actors) and crew (director)
- filter movies by:
  - genre(s)
  - release year range
  - budget range
  - revenue range
  - actor
  - director
- search by movie title / actor / director

The dataset we use is from Kaggle: **The Movies Dataset**.

---

## Frontend vs Backend (easy example)

Think of it like a restaurant:

- **Frontend** = waiter + menu (what the customer sees)
- **Backend** = kitchen (does the work)
- **Database** = store room (where ingredients/data are kept)

When the user clicks “Action movies from 2010 to 2020”:
- Frontend sends the request to backend.
- Backend asks the database for matching movies.
- Backend returns only the needed results.
- Frontend shows them nicely on screen.

---

## What exactly is Backend?

Backend is the part that:
- talks to the database
- runs search and filter logic
- sends results back to the website
- keeps things fast and organized

Backend is usually made of:
- a **server** (a program running on your computer / cloud)
- an **API** (URLs/endpoints that the frontend can call)
- a **database** (where we store movie data)

---

## What is an API? (super simple)

API is a set of “doors” the frontend can knock on.

Example:
- Frontend knocks on: `GET /movies?genres=Action&yearFrom=2010&yearTo=2020`
- Backend opens the door, finds the movies, and replies with data (JSON).

---

## Why do we need a database?

The dataset is large. If we keep it only in CSV files:
- searching will be slow
- filtering will be messy
- joining cast + crew will be hard

Database helps because:
- it keeps data structured
- it supports fast filtering and searching
- we can create indexes for speed

---

## Which database type is best for this project?

### Recommended: SQL (Relational database)

Because the data has **relationships**:
- One movie has many genres
- One movie has many actors
- One actor is in many movies
- One director directs many movies

SQL is great at relationships + filtering.

Possible SQL options:
- **SQLite** (easy for local development)
- **PostgreSQL** or **MySQL** (stronger for production / hosting)

For coursework, SQLite is often enough and simplest.

---

## What does “data cleaning” mean for this dataset?

The Kaggle dataset includes columns that look like JSON but are stored as text inside CSV.
Examples:
- `genres` might be something like `[{"id": 28, "name": "Action"}]`
- `cast` and `crew` are also stored like long JSON text

Cleaning means:
- parsing that text into real lists/objects
- handling missing values (blank budget, blank revenue, missing dates)
- converting strings to numbers/dates
- making it fit the database tables we design

---

## Database design (tables) — simple explanation

We will create tables like this:

### 1) `movies`
Stores one row per movie:
- `id`
- `title`
- `overview`
- `release_date` (and/or `release_year`)
- `runtime`
- `budget`
- `revenue`

### 2) `genres`
Stores one row per genre:
- `id`
- `name` (Action, Comedy, Drama, etc.)

### 3) `people`
Stores one row per person:
- `id`
- `name` (actor/director)

### 4) Link tables (because “many-to-many”)

Because one movie can have many genres, we use a link table:

#### `movie_genres`
- `movie_id`
- `genre_id`

Because a movie has many cast members:

#### `movie_cast`
- `movie_id`
- `person_id`
- (optional) `character`
- (optional) `cast_order`

Because a movie has crew members (director, producer, etc.):

#### `movie_crew`
- `movie_id`
- `person_id`
- `job` (e.g. Director)

This design:
- avoids duplicated data
- makes filtering easier
- keeps the database clean

---

## What filters/search must we support? (from the assignment)

Backend must support:
- **Genres**: one or more selected genres (AND/OR logic depends on UI choice)
- **Years**: released in selected years (usually a range `yearFrom`–`yearTo`)
- **Budget range**
- **Revenue range**
- **Actor filter**: “movies starring this actor”
- **Director filter**: “movies directed by this director”
- **Search**: title or actor or director

---

## Backend endpoints we will build (API plan)

### 1) `GET /movies`
Returns a list of movies for the grid/list view.

Supports query parameters:
- `q` = search text (title OR actor OR director)
- `genres` = comma-separated list (e.g. `Action,Adventure`)
- `yearFrom`, `yearTo`
- `budgetMin`, `budgetMax`
- `revenueMin`, `revenueMax`
- `actor` = actor name (string)
- `director` = director name (string)
- `page`, `pageSize` (pagination)

Example requests:
- `/movies?q=inception`
- `/movies?genres=Action,Adventure&yearFrom=2010&yearTo=2020`
- `/movies?budgetMin=0&budgetMax=5000000`
- `/movies?revenueMin=200000000`
- `/movies?actor=Leonardo%20DiCaprio`
- `/movies?director=Christopher%20Nolan`

### 2) `GET /movies/{id}`
Returns full details for one movie:
- movie info
- all genres
- cast list
- crew list (or at least director)

### 3) `GET /genres`
Returns all genres (for the filter UI dropdown/checkbox list).

### 4) (Optional but useful) `GET /people/search?q=...`
Helps autocomplete actor/director names.

---

## What data will the backend return? (keep it small)

To keep performance good:
- **List page** should return only what it needs:
  - `id`, `title`, `release_year`, `runtime`, `overview_short`, `genres`
- **Details page** can return everything:
  - full overview + cast + crew + budgets

This matches the requirement: “Only sending data that is required”.

---

## How do we keep it fast? (performance)

We will do a few important things:
- **Indexes** on important columns:
  - `movies(release_year)`
  - `movies(budget)`
  - `movies(revenue)`
  - `people(name)`
  - link table keys (`movie_id`, `person_id`, `genre_id`)
- **Pagination** so we don’t send thousands of rows at once
- **Single query** approach when possible (avoid many repeated queries)

---

## Step-by-step build plan (what we will actually do)

### Step 1 — Pick stack
Example stack (simple):
- Backend: Python + FastAPI
- Database: SQLite

---

## What is FastAPI? (very simple)

FastAPI is a Python tool (a **web framework**) that helps us build a backend **server** quickly.

Think of FastAPI like a **reception desk**:
- The frontend sends a request (a question) to the backend.
- FastAPI receives it.
- It sends that question to our code (and database).
- Then it sends the answer back as **JSON**.

### Why we like FastAPI for this project
- It is **fast** and modern.
- It is easy to build **API endpoints** like `/movies`.
- It automatically creates **API docs** in the browser (so we can test endpoints easily).

---

## How backend + FastAPI works (simple flow)

1. User clicks filters on the website (frontend).
2. Frontend sends a request like:
   - `/movies?genres=Action&yearFrom=2010&yearTo=2020`
3. FastAPI receives the request.
4. Our backend code builds a database query.
5. Database returns the matching movies.
6. Backend returns the movies as JSON.
7. Frontend shows them on the screen.

---

## What is an “endpoint” in FastAPI?

An endpoint is a **function** connected to a URL.

Example:
- URL: `/movies`
- That URL is linked to a Python function that returns movie data.

So when someone opens `/movies?...`, FastAPI runs that function and returns the result.

---

## What is JSON? (what the backend sends)

JSON is just a simple text format used to send data.

It looks like:
- words inside quotes
- lists inside `[ ]`
- objects inside `{ }`

Example movie JSON:

```json
{
  "id": 123,
  "title": "Inception",
  "release_year": 2010,
  "genres": ["Action", "Sci-Fi"],
  "runtime": 148
}
```

---

## How FastAPI connects to the database

FastAPI itself does not “store data”.
It only handles requests and responses.

To store and read data, our backend will use:
- a database (SQLite / MySQL / Postgres)
- SQL queries (or an ORM like SQLAlchemy)

So the backend has 2 big jobs:
- **FastAPI**: receive request and return JSON
- **Database layer**: run the real query and fetch rows

---

## How the frontend will talk to the backend (simple)

Frontend will use `fetch()` in JavaScript.

Example idea (not final code):

```js
fetch("http://localhost:8000/movies?genres=Action&yearFrom=2010&yearTo=2020")
  .then((r) => r.json())
  .then((data) => console.log(data));
```

So the frontend does not “read the database”.
Frontend only talks to backend.

---

## Running FastAPI (how we start the backend server)

When we build the backend, we will run something like:
- start server on `http://localhost:8000`
- then we can open:
  - API itself: `http://localhost:8000/movies`
  - Auto docs: `http://localhost:8000/docs`

(This helps us test the backend without the frontend.)

### Step 2 — Create database schema
Create tables:
- `movies`, `genres`, `people`, `movie_genres`, `movie_cast`, `movie_crew`

### Step 3 — Import + clean dataset
- read Kaggle CSV files
- parse JSON-like columns
- insert data into normalized tables

### Step 4 — Build API endpoints
- `/movies` with filters/search/pagination
- `/movies/{id}` for details
- `/genres`

### Step 5 — Connect frontend to backend
- Replace the sample movies in the UI with API calls.
- Display results from real database.

### Step 6 — Testing
Test:
- each filter
- search
- performance (response time)

---

## Short glossary (tiny dictionary)

- **Backend**: server logic behind the website
- **Frontend**: what the user sees in the browser
- **Database**: where data is stored
- **API**: endpoints/URLs frontend calls
- **Endpoint**: one API “door” like `/movies`
- **Query parameters**: filters in the URL after `?`
- **Schema**: tables + columns design
- **ERD**: diagram showing table relationships
- **Index**: database “speed booster” for searching
- **Pagination**: showing results page by page

