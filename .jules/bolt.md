## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2025-02-18 - [Subquery Optimization for Django Aggregations]
**Learning:** When generating summary statistics for models that have a one-to-many relationship (e.g. `TrainingBlock` and `RunActivity`), using `prefetch_related` and doing math in Python loops forces the ORM to load all related items into memory as complete Django model instances. This causes high CPU, serialization, and memory overhead as the dataset grows.
**Action:** Use `annotate` with `Subquery`, `OuterRef`, `Sum`, and `Count` to perform the mathematical aggregations at the database level. This dramatically reduces memory and execution time.
