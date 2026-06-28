## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2024-06-28 - Subqueries vs Annotate Fanout
**Learning:** When performing multiple one-to-many aggregations (e.g. counting both Runs and B-Races for a Training Block), standard `.annotate(Sum(...))` can cause severe SQL JOIN fanout, returning inflated numbers. In this codebase, it doubled `distance_km`.
**Action:** Use `Subquery` with `OuterRef` and `Coalesce` to safely isolate aggregations and push them to the database safely, avoiding N+1 loops in Python and JOIN cartesian products.
