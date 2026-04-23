from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from pydantic import EmailStr, Field


class GenreOut(BaseModel):
    genre_id: int
    genre_name: str


class MovieListItem(BaseModel):
    movie_id: int
    title: str
    overview: str | None = None
    release_year: int | None = None
    runtime: int | None = None
    budget: int | None = None
    revenue: int | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    genres: list[str] = []
    poster_path: str | None = None


class MovieDetail(BaseModel):
    movie_id: int
    title: str
    overview: str | None = None
    release_date: date | None = None
    release_year: int | None = None
    runtime: int | None = None
    budget: int | None = None
    revenue: int | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    adult: bool | None = None
    original_language: str | None = None
    tagline: str | None = None
    poster_path: str | None = None
    genres: list[GenreOut] = []
    cast: list[str] = []
    director: str | None = None


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)  # username OR email
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str


class ReviewOut(BaseModel):
    id: int
    movie_id: int
    user_id: int
    username: str
    rating: int
    review_text: str | None = None
    created_at: str


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str | None = Field(default=None, max_length=1000)

