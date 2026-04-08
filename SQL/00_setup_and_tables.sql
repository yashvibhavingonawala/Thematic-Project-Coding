-- Deduplicated MySQL script generated from attached CSV files
-- Removes duplicate primary/composite-key rows, skips invalid foreign keys, omits null/blank columns from INSERT statements.
-- If you are using the Mudfoot Server then don't run the first 2 lines as they won't run but if you are using your own server then you can run the whole script.

CREATE DATABASE IF NOT EXISTS movie_db;
USE movie_db;

DROP TABLE IF EXISTS movie_spoken_language;
DROP TABLE IF EXISTS movie_production_country;
DROP TABLE IF EXISTS movie_production_company;
DROP TABLE IF EXISTS movie_genre;
DROP TABLE IF EXISTS movie_collection;
DROP TABLE IF EXISTS movie;
DROP TABLE IF EXISTS spoken_language;
DROP TABLE IF EXISTS production_country;
DROP TABLE IF EXISTS production_company;
DROP TABLE IF EXISTS genre;
DROP TABLE IF EXISTS collection;

CREATE TABLE collection (
    collection_id INT NOT NULL,
    collection_name VARCHAR(255) NOT NULL,
    PRIMARY KEY (collection_id)
) ENGINE=InnoDB;

CREATE TABLE genre (
    genre_id INT NOT NULL,
    genre_name VARCHAR(150) NOT NULL,
    PRIMARY KEY (genre_id)
) ENGINE=InnoDB;

CREATE TABLE production_company (
    production_company_id INT NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    PRIMARY KEY (production_company_id)
) ENGINE=InnoDB;

CREATE TABLE production_country (
    country_id VARCHAR(10) NOT NULL,
    country_name VARCHAR(150) NOT NULL,
    PRIMARY KEY (country_id)
) ENGINE=InnoDB;

CREATE TABLE spoken_language (
    spoken_language_id VARCHAR(10) NOT NULL,
    language_name VARCHAR(150) NOT NULL,
    PRIMARY KEY (spoken_language_id)
) ENGINE=InnoDB;

CREATE TABLE movie (
    movie_id INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    overview TEXT,
    release_date DATE,
    release_year INT,
    runtime INT,
    budget BIGINT,
    revenue BIGINT,
    vote_average DECIMAL(4,2),
    vote_count INT,
    adult BOOLEAN,
    original_language VARCHAR(10),
    tagline VARCHAR(500),
    PRIMARY KEY (movie_id)
) ENGINE=InnoDB;

CREATE TABLE movie_collection (
    movie_id INT NOT NULL,
    collection_id INT NOT NULL,
    PRIMARY KEY (movie_id, collection_id),
    CONSTRAINT fk_movie_collection_movie FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_movie_collection_collection FOREIGN KEY (collection_id) REFERENCES collection(collection_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE movie_genre (
    movie_id INT NOT NULL,
    genre_id INT NOT NULL,
    PRIMARY KEY (movie_id, genre_id),
    CONSTRAINT fk_movie_genre_movie FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_movie_genre_genre FOREIGN KEY (genre_id) REFERENCES genre(genre_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE movie_production_company (
    movie_id INT NOT NULL,
    production_company_id INT NOT NULL,
    PRIMARY KEY (movie_id, production_company_id),
    CONSTRAINT fk_movie_production_company_movie FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_movie_production_company_company FOREIGN KEY (production_company_id) REFERENCES production_company(production_company_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE movie_production_country (
    movie_id INT NOT NULL,
    country_id VARCHAR(10) NOT NULL,
    PRIMARY KEY (movie_id, country_id),
    CONSTRAINT fk_movie_production_country_movie FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_movie_production_country_country FOREIGN KEY (country_id) REFERENCES production_country(country_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE movie_spoken_language (
    movie_id INT NOT NULL,
    spoken_language_id VARCHAR(10) NOT NULL,
    PRIMARY KEY (movie_id, spoken_language_id),
    CONSTRAINT fk_movie_spoken_language_movie FOREIGN KEY (movie_id) REFERENCES movie(movie_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_movie_spoken_language_language FOREIGN KEY (spoken_language_id) REFERENCES spoken_language(spoken_language_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
