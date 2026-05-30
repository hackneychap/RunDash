## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2025-05-30 - [Dashboard SQLite Query Optimization]
**Learning:** For dashboard view performance with SQLite, fetching raw fields using Django's `.values()` and aggregating in Python memory is significantly faster than using multiple ORM `.aggregate()`, `TruncWeek`, and `TruncMonth` grouping queries. The ORM queries added substantial overhead compared to processing in memory.
**Action:** When performing complex time-series aggregations on datasets from SQLite, prefer fetching all necessary raw data with a single `.values()` query and process the aggregations in Python.
