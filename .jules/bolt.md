## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2024-06-07 - [Django Cache Optimization on Heavy Aggregate Queries]
**Learning:** The dashboard view performs multiple complex aggregations (`Sum`, `Avg`, `TruncWeek`, `TruncMonth`) on the entire `RunActivity` dataset on every page load.
**Action:** Utilize Django's built-in `cache` to store the output context for expensive views, drastically reducing page render time. Always ensure the cache is explicitly invalidated when the underlying data is successfully refreshed (e.g., when the background import task completes).
