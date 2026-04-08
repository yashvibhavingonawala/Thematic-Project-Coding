This folder contains the SQL script split into smaller chunks for easier execution in VS Code.

Recommended run order:
00_setup_and_tables.sql
01_collection.sql
02_genre.sql
03_production_company.sql
04_production_country.sql
05_spoken_language.sql
06_movie.sql
07_movie_collection.sql
08_movie_genre.sql
09_movie_production_company.sql
10_movie_production_country.sql
11_movie_spoken_language.sql

Run them in this exact order because the later files depend on foreign keys.
