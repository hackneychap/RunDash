## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2026-05-29 - [SQLite/Django Query Optimization for Dashboard Load]
**Learning:** Running multiple `TruncWeek` and `TruncMonth` queries and `.aggregate()` with Django's ORM on SQLite is significantly slower than doing a single `.values()` query and looping over the data in Python (reducing ~1.1s database load to ~0.5s for 500 rows). SQLite aggregations with Trunc funcations have non-trivial overhead compared to an in-memory Python loop.
**Action:** For complex grouped stats where all the source data is needed anyway, try fetching the raw data once and doing the aggregation in Python.
