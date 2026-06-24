## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2025-02-18 - [Django Caching of Unevaluated QuerySets]
**Learning:** Caching raw  objects in Django only pickles the query structure, not the underlying data. This results in the database being hit every time the view reads from the cache to render the template.
**Action:** When storing database query results in the Django cache, always explicitly evaluate the QuerySet into memory (e.g., using ) before writing to the cache.

## 2025-02-18 - [Django Caching of Unevaluated QuerySets]
**Learning:** Caching raw QuerySet objects in Django only pickles the query structure, not the underlying data. This results in the database being hit every time the view reads from the cache to render the template.
**Action:** When storing database query results in the Django cache, always explicitly evaluate the QuerySet into memory (e.g., using `list(queryset)`) before writing to the cache.
