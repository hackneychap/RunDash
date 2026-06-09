## 2025-02-18 - [SQLite Query Optimization for Garmin Data Sync]
**Learning:** The application syncs run activities from a local GarminDB SQLite database, which previously transferred thousands of old records into Python memory only to discard them based on a 2-year cutoff. Furthermore, date parsing using `strptime` is significantly slower compared to `fromisoformat`.
**Action:** When querying large local SQLite databases (like GarminDB), push down WHERE clauses to filter large datasets at the database level instead of in-memory. For date string parsing, use string slicing and `datetime.date.fromisoformat` over `datetime.datetime.strptime` where the string format allows (e.g., extracting "YYYY-MM-DD" from "YYYY-MM-DD HH:MM:SS").

## 2023-10-27 - [Caching Bulk Import Bypass]
**Learning:** Django's `bulk_create` and `bulk_update` methods bypass model signals like `post_save` and `post_delete`. Using signals to clear caches related to models updated via bulk operations will fail to invalidate the cache during those operations.
**Action:** When implementing model-level cache invalidation via signals, also identify any background tasks or bulk imports that modify the data. Explicitly invalidate the cache after those bulk operations complete to ensure data consistency.
