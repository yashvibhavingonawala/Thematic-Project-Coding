# Movie Database Presentation Tool (Template)

This is a frontend starter template for your coursework project.

## Included

- Responsive layout with:
  - Search bar for title / actor / director
  - Genre multi-select filters
  - Release year range filter
  - Budget range filter
  - Revenue range filter
  - Actor and director text filters
- Movie card grid with expandable sections for:
  - Cast and crew
  - Financials
- Sample movie data and client-side filtering logic

## Run

Because this is a static template, you can open `index.html` directly in your browser, or run a local static server.

Example (Python):

```bash
cd "/Users/yashvigonawala/Thematic project"
python3 -m http.server 5500
```

Then open `http://localhost:5500`.

## Files

- `index.html` - page structure
- `styles.css` - styling and responsive layout
- `app.js` - sample data + filter logic

## Next Step (when backend is ready)

1. Replace `sampleMovies` in `app.js` with API responses.
2. Add an endpoint such as:
   - `GET /movies?genres=Action,Adventure&yearFrom=2010&yearTo=2020...`
3. Trigger API requests on `Apply Filters` button click.
4. Keep response payload minimal (only fields needed on screen) for performance.
