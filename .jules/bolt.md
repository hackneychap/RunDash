## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2024-05-18 - [Django QuerySet Pickling Context Caching]
**Learning:** Caching a full Django context dictionary that contains QuerySets (like `runs = RunActivity.objects.all().order_by('date')`) means Django evaluates and pickles all records into memory when saving to cache. As the dataset grows, this consumes significant cache memory (Redis/Memcached/DB) and slows down serialization.
**Action:** When caching dashboard or view contexts, cache either the fully rendered HTML template (`@cache_page`) or cache only the aggregated numerical data/primitives instead of the raw QuerySet objects.
