These CSV files match the cleaned MySQL tables and are ready to upload separately.

Files included:
- collection.csv
- genre.csv
- production_company.csv
- production_country.csv
- spoken_language.csv
- movie.csv
- movie_collection.csv
- movie_genre.csv
- movie_production_company.csv
- movie_production_country.csv
- movie_spoken_language.csv

Notes:
- movie.csv uses movie_id instead of id, to match the SQL table.
- Duplicate rows were removed.
- Junction tables were filtered so they only contain valid foreign-key references.
- Namibia (NA) is included in production_country.csv directly below Thailand (TH).
