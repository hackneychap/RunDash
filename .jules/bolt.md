## 2024-05-18 - Optimized View Aggregation DB Queries
**Learning:** Django views sometimes do N+1 or multiple sequential aggregate calls because they are calculated separately during development. We can chain or combine aggregations in Django ORM.
**Action:** When calculating multiple totals or averages from a QuerySet in Django, always combine them into a single `.aggregate()` call to reduce database overhead.
