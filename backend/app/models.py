from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Date, DECIMAL, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime


class Base(DeclarativeBase):
    pass


class Movie(Base):
    __tablename__ = "movie"

    movie_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    revenue: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    vote_average: Mapped[object | None] = mapped_column(DECIMAL(4, 2), nullable=True)
    vote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adult: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    original_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Genre(Base):
    __tablename__ = "genre"

    genre_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    genre_name: Mapped[str] = mapped_column(String(150))


class MovieGenre(Base):
    __tablename__ = "movie_genre"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movie.movie_id"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genre.genre_id"), primary_key=True)


class Person(Base):
    __tablename__ = "person"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)


class MovieCast(Base):
    __tablename__ = "movie_cast"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movie.movie_id"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.person_id"), primary_key=True)
    character: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cast_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MovieCrew(Base):
    __tablename__ = "movie_crew"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movie.movie_id"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.person_id"), primary_key=True)
    job: Mapped[str] = mapped_column(String(100), primary_key=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_age_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    verification_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    verified_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    birth_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    is_adult: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")


class Review(Base):
    __tablename__ = "review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movie.movie_id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1..5 stars
    review_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MovieRecommendation(Base):
    __tablename__ = "movie_recommendations"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movie.movie_id"), primary_key=True)
    recommended_movie_id: Mapped[int] = mapped_column(ForeignKey("movie.movie_id"), primary_key=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

